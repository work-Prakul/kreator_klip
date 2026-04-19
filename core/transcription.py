import asyncio
import os
import logging
from typing import List, Dict, Any

import ffmpeg
from faster_whisper import WhisperModel
from utils.hardware import vram_flash
from core.transcription_config import get_whisper_config
from utils.hardware_profile import HardwareProfile


def _parse_transcript_segments(raw_segments, segment_start: float) -> List[Dict[str, Any]]:
    segment_data = []
    for segment in raw_segments:
        words = []
        for word in segment.words:
            words.append({
                "word": word.word,
                "start": word.start + segment_start,
                "end": word.end + segment_start,
                "probability": word.probability
            })
        segment_data.append({
            "start": segment.start + segment_start,
            "end": segment.end + segment_start,
            "text": segment.text,
            "words": words
        })
    return segment_data


def _load_whisper_model(model_size: str, device: str, compute_type: str):
    return WhisperModel(model_size, device=device, compute_type=compute_type)


def _try_whisper_model_load(model_size: str, device: str, compute_type: str):
    try:
        return _load_whisper_model(model_size, device, compute_type)
    except Exception as exc:
        logging.warning(f"Whisper model load failed on {device}:{compute_type}: {exc}")
        return None


def transcribe_audio(audio_path: str, model_size: str = "base", device: str = "cuda", compute_type: str = "float32") -> List[Dict[str, Any]]:
    logging.info(f"Loading Whisper model '{model_size}' on {device} ({compute_type})...")
    model = _try_whisper_model_load(model_size, device, compute_type)
    if model is None and device == "cuda" and compute_type == "float16":
        logging.info("GPU float16 unsupported, retrying with float32.")
        model = _try_whisper_model_load(model_size, device, "float32")
    if model is None and device != "cpu":
        logging.info("Falling back to CPU int8 transcription.")
        model = _try_whisper_model_load(model_size, "cpu", "int8")
    # CPU-only: int8 quantization is required for efficient inference
    if model is None and device == "cpu":
        logging.info("CPU requires int8 quantization, retrying...")
        model = _try_whisper_model_load(model_size, "cpu", "int8")

    if model is None:
        logging.error("Transcription failed: no usable Whisper model could be loaded.")
        return []

    try:
        raw_segments, _ = model.transcribe(audio_path, beam_size=5, word_timestamps=True)
        segment_data = _parse_transcript_segments(raw_segments, 0.0)
        return segment_data
    except Exception as exc:
        logging.error(f"Transcription runtime failed on {audio_path}: {exc}")
        return []
    finally:
        del model
        vram_flash()


def _ensure_segment_audio(source_audio: str, start_time: float, end_time: float, temp_dir: str, index: int) -> str:
    os.makedirs(temp_dir, exist_ok=True)
    segment_path = os.path.join(temp_dir, f"whisper_segment_{index}.wav")
    ffmpeg.input(source_audio, ss=start_time, to=end_time).output(
        segment_path,
        acodec="pcm_s16le",
        ac=1,
        ar="16000"
    ).overwrite_output().run(quiet=True)
    return segment_path


def _sync_transcribe_batch(segment_specs: List[Dict[str, Any]], model_size: str, hardware_profile: HardwareProfile) -> List[Dict[str, Any]]:
    whisper_cfg = get_whisper_config(hardware_profile)
    device = whisper_cfg["device"]
    compute_type = whisper_cfg["compute_type"]

    model = _try_whisper_model_load(model_size, device, compute_type)
    if model is None and device == "cuda" and compute_type == "float16":
        logging.info("GPU float16 unsupported for batch transcription, retrying with float32.")
        model = _try_whisper_model_load(model_size, device, "float32")
    if model is None and device != "cpu":
        logging.info("Falling back to CPU int8 transcription.")
        model = _try_whisper_model_load(model_size, "cpu", "int8")
    # CPU-only: int8 quantization is required for efficient inference
    if model is None and device == "cpu":
        logging.info("CPU requires int8 quantization, retrying...")
        model = _try_whisper_model_load(model_size, "cpu", "int8")

    if model is None:
        logging.error("Batch transcription failed: no usable Whisper model available.")
        return []

    output = []
    for spec in segment_specs:
        path = spec["path"]
        start_offset = spec.get("start", 0.0)
        try:
            raw_segments, _ = model.transcribe(path, beam_size=5, word_timestamps=True)
            output.extend(_parse_transcript_segments(raw_segments, start_offset))
        except Exception as exc:
            logging.warning(f"Segment transcription failed for {path}: {exc}")
            continue

    del model
    vram_flash()
    return output


async def transcribe_segments_batched(
    segment_specs: List[Dict[str, Any]],
    model_size: str,
    hardware_profile: HardwareProfile,
    max_limit: int = 8
) -> List[Dict[str, Any]]:
    if not segment_specs:
        return []

    batch_size = min(max(int(hardware_profile.vram_gb * 2), 1), max_limit)
    all_results: List[Dict[str, Any]] = []

    for i in range(0, len(segment_specs), batch_size):
        batch = segment_specs[i:i + batch_size]
        batch_results = await asyncio.to_thread(_sync_transcribe_batch, batch, model_size, hardware_profile)
        all_results.extend(batch_results)

    return all_results


def format_time_ass(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centisecs = int((seconds - int(seconds)) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"


def generate_ass(segment_data: List[Dict[str, Any]], output_ass_path: str):
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,90,&H0000FFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,2,10,10,250,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    with open(output_ass_path, "w", encoding="utf-8") as f:
        f.write(header)
        chunk_size = 3
        for seg in segment_data:
            words = seg["words"]
            for i in range(0, len(words), chunk_size):
                chunk = words[i:i + chunk_size]
                if not chunk:
                    continue
                start_time = format_time_ass(chunk[0]["start"])
                end_time = format_time_ass(chunk[-1]["end"])
                text = " ".join([w["word"] for w in chunk]).strip()
                f.write(f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text}\n")
    logging.info(f"Finisher: Created styled subtitles at {output_ass_path}")


def run_finisher_stage(trimmed_clip_path: str, final_output_path: str, config: Dict[str, Any], profile: Dict[str, Any]) -> bool:
    logging.info("--- STAGE 4: THE FINISHER ---")
    try:
        # Verify input file exists
        if not os.path.exists(trimmed_clip_path):
            logging.error(f"Finisher: Input clip not found: {trimmed_clip_path}")
            return False
        
        # Ensure output directory exists
        output_dir = os.path.dirname(final_output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        temp_audio = trimmed_clip_path.replace(".mp4", "_audio.wav")
        (
            ffmpeg
            .input(trimmed_clip_path)
            .output(temp_audio, acodec="pcm_s16le", ac=1, ar="16000")
            .overwrite_output()
            .run(quiet=True)
        )

        segment_data = transcribe_audio(
            temp_audio,
            model_size=profile.get("whisper_model", "base"),
            device=profile.get("device", "cpu"),
            compute_type=profile.get("compute_type", "int8")
        )

        ass_path = trimmed_clip_path.replace(".mp4", ".ass")
        generate_ass(segment_data, ass_path)

        logging.info("Finisher: Burning subtitles into final video...")
        safe_ass_path = ass_path.replace("\\", "/").replace(":", "\\:")
        force_cpu = config.get("hardware_overrides", {}).get("force_cpu", False)

        stream = ffmpeg.input(trimmed_clip_path)
        video = stream.video.filter("ass", safe_ass_path)
        audio = stream.audio

        try:
            if not force_cpu:
                ffmpeg.output(video, audio, final_output_path, vcodec="h264_nvenc", preset=config.get("render_preset", "p4")).overwrite_output().run(quiet=True)
            else:
                ffmpeg.output(video, audio, final_output_path, vcodec="libx264", preset="fast").overwrite_output().run(quiet=True)
        except ffmpeg.Error as exc:
            logging.warning(f"Finisher: GPU encode failed ({exc}), falling back to CPU.")
            ffmpeg.output(video, audio, final_output_path, vcodec="libx264", preset="fast").overwrite_output().run(quiet=True)

        logging.info(f"Finisher: Successfully generated final short -> {final_output_path}")
        for path in [temp_audio, ass_path]:
            if os.path.exists(path):
                os.remove(path)
        return True
    except Exception as exc:
        logging.error(f"Finisher: Failed to finalize clip {trimmed_clip_path}: {exc}")
        return False
