from faster_whisper import WhisperModel
import os
import logging
import ffmpeg
from utils.hardware import vram_flash

def transcribe_audio(audio_path: str, model_size: str = "base", device: str = "cuda", compute_type: str = "float16"):
    """
    Core transcription function used by Scanner and Finisher.
    Returns segments with word-level timestamps.
    """
    logging.info(f"Loading Whisper model '{model_size}' to {device}...")
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    
    segments, info = model.transcribe(audio_path, beam_size=5, word_timestamps=True)
    
    segment_data = []
    for segment in segments:
        words = []
        for word in segment.words:
            words.append({
                "word": word.word,
                "start": word.start,
                "end": word.end,
                "probability": word.probability
            })
        segment_data.append({
            "start": segment.start,
            "end": segment.end,
            "text": segment.text,
            "words": words
        })
        
    del model
    vram_flash()
        
    return segment_data

def format_time_ass(seconds: float) -> str:
    """Converts seconds into ASS time format (H:MM:SS.cs)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centisecs = int((seconds - int(seconds)) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"

def generate_ass(segment_data: list, output_ass_path: str):
    """
    Generates a heavily styled Advanced SubStation Alpha (.ass) file.
    """
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
        
        # Max 3-4 words per subtitle for Reel/TikTok pacing
        chunk_size = 3
        for seg in segment_data:
            words = seg['words']
            for i in range(0, len(words), chunk_size):
                chunk = words[i:i+chunk_size]
                if not chunk:
                    continue
                    
                start_time = format_time_ass(chunk[0]['start'])
                end_time = format_time_ass(chunk[-1]['end'])
                text = " ".join([w['word'] for w in chunk]).strip()
                
                # Format: Dialogue: 0,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
                f.write(f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text}\n")
                
    logging.info(f"Finisher: Created styled subtitles at {output_ass_path}")

def run_finisher_stage(trimmed_clip_path: str, final_output_path: str, config: dict, profile: dict):
    """
    Stage 4: The Finisher.
    Reads the 30-second trimmed clip, transcodes word-level captions, and burns them into a final video.
    """
    logging.info("--- STAGE 4: THE FINISHER ---")
    try:
        # Extract audio from the 30s clip for Whisper
        temp_audio = trimmed_clip_path.replace(".mp4", "_audio.wav")
        (
            ffmpeg
            .input(trimmed_clip_path)
            .output(temp_audio, acodec='pcm_s16le', ac=1, ar='16000')
            .overwrite_output()
            .run(quiet=True)
        )
        
        # Transcribe
        segment_data = transcribe_audio(
            temp_audio, 
            model_size=profile["whisper_model"], 
            device=profile["device"], 
            compute_type=profile["compute_type"]
        )
        
        # Generate styled .ass
        ass_path = trimmed_clip_path.replace(".mp4", ".ass")
        generate_ass(segment_data, ass_path)
        
        # Burn into video
        logging.info("Finisher: Burning subtitles into final video...")
        
        safe_ass_path = ass_path.replace('\\', '/').replace(':', '\\:')
        
        hardware_overrides = config.get("hardware_overrides", {})
        force_cpu = hardware_overrides.get("force_cpu", False)
        
        stream = ffmpeg.input(trimmed_clip_path)
        video = stream.video.filter('ass', safe_ass_path)
        audio = stream.audio
        
        enc_success = False
        if not force_cpu:
            try:
                out = ffmpeg.output(video, audio, final_output_path, vcodec='h264_nvenc', preset='fast')
                out = out.overwrite_output()
                ffmpeg.run(out, quiet=True)
                enc_success = True
            except ffmpeg.Error:
                logging.warning("Finisher: NVENC burn-in failed, fallback to CPU.")
                
        if not enc_success:
            out = ffmpeg.output(video, audio, final_output_path, vcodec='libx264', preset='fast')
            out = out.overwrite_output()
            ffmpeg.run(out, quiet=True)
            
        logging.info(f"Finisher: Successfully generated final short -> {final_output_path}")
        
        # Cleanup temp
        for path in [temp_audio, ass_path]:
            if os.path.exists(path):
                os.remove(path)
                
        return True
    except Exception as e:
        logging.error(f"Finisher: Failed to finalize clip {trimmed_clip_path}: {e}")
        return False
