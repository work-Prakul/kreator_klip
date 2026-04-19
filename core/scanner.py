import os
import logging
from typing import Dict, Any, List

import ffmpeg
from utils.hardware import vram_flash
from utils.hardware_profile import profile_hardware, HardwareProfile
from core.transcription import _sync_transcribe_batch
from core.audio import extract_audio, analyze_audio_spikes, merge_nearby_rois
from core.transcription_config import get_whisper_config
from core.scoring import rank_events


def _extract_audio_segment(source_audio: str, start_time: float, end_time: float, temp_dir: str, index: int) -> str:
    os.makedirs(temp_dir, exist_ok=True)
    segment_path = os.path.join(temp_dir, f"scanner_segment_{index}.wav")
    ffmpeg.input(source_audio, ss=start_time, to=end_time).output(
        segment_path,
        acodec="pcm_s16le",
        ac=1,
        ar="16000"
    ).overwrite_output().run(quiet=True)
    return segment_path


def run_scanner(video_path: str, config: Dict[str, Any], ui_callback):
    """Stage 1: The Ear. Detects audio peaks, transcribes small segments, and ranks candidates."""
    ui_callback("Scanner: Extracting audio for modular analysis...")
    temp_dir = "temp"
    os.makedirs(temp_dir, exist_ok=True)
    temp_audio = os.path.join(temp_dir, "scanner_audio.wav")

    extract_audio(video_path, temp_audio)

    ui_callback("Scanner: Detecting audio spikes...")
    threshold_percentile = float(config.get("audio_threshold", 95.0))
    rois = analyze_audio_spikes(temp_audio, threshold_percentile=threshold_percentile)
    ui_callback(f"Scanner: Found {len(rois)} raw audio spike regions.")

    if not rois:
        ui_callback("Scanner: No spike regions detected, aborting scan.")
        if os.path.exists(temp_audio):
            os.remove(temp_audio)
        return []

    merged_rois = merge_nearby_rois(rois, max_gap=3.0, padding=1.0)
    ui_callback(f"Scanner: Consolidated into {len(merged_rois)} candidate windows.")

    hardware_profile = profile_hardware(config.get("hardware_overrides", {}))
    whisper_cfg = get_whisper_config(hardware_profile)

    segment_specs: List[Dict[str, Any]] = []
    for index, roi in enumerate(merged_rois):
        start = max(0.0, roi["start"] - 1.0)
        end = roi["end"] + 1.0
        segment_path = _extract_audio_segment(temp_audio, start, end, temp_dir, index)
        segment_specs.append({"path": segment_path, "start": start, "end": end, "energy": roi["energy"]})

    ui_callback("Scanner: Transcribing candidate audio segments...")
    try:
        # Use synchronous batching - we're already in a thread via asyncio.to_thread
        segment_data = _sync_transcribe_batch(
            segment_specs,
            whisper_cfg["model_size"],
            hardware_profile
        )
    except Exception as exc:
        logging.error(f"Batch transcription failed: {exc}")
        segment_data = []

    all_words = []
    for segment in segment_data:
        all_words.extend(segment["words"])

    candidates: List[Dict[str, Any]] = []
    for roi in merged_rois:
        keywords = []
        keyword_hits = 0
        for word in all_words:
            if word["start"] >= roi["start"] and word["end"] <= roi["end"]:
                clean_word = word["word"].lower().strip(" \t\n\r.,!?\"'")
                if any(kw in clean_word for kw in config.get("game_profiles", {}).get(config.get("current_game", "valorant"), {}).get("keywords", [])):
                    keyword_hits += 1
                    keywords.append(clean_word)

        candidates.append({
            "start": roi["start"],
            "end": roi["end"],
            "energy": roi["energy"],
            "keyword_hits": keyword_hits,
            "keywords": list(set(keywords))
        })

    ranked_events = rank_events(candidates, config)
    max_clips = int(config.get("max_clips", 15))
    threshold = float(config.get("audio_threshold", 0.7))
    selected = [event for event in ranked_events if event["score"] >= threshold]
    if not selected:
        selected = ranked_events[:max_clips]
    else:
        selected = selected[:max_clips]

    final_events = []
    for event in selected:
        final_events.append({
            "start": event["start"],
            "end": event["end"],
            "score": event["score"],
            "keywords": event.get("keywords", [])
        })

    ui_callback(f"Scanner: Finalized {len(final_events)} candidate clips.")

    for spec in segment_specs:
        try:
            if os.path.exists(spec["path"]):
                os.remove(spec["path"])
        except OSError:
            pass
    if os.path.exists(temp_audio):
        os.remove(temp_audio)

    return final_events
