"""
KREATOR KLIP - Audio Processing Module
Extracts and analyzes audio for spike detection.
"""
import ffmpeg
import librosa
import numpy as np
import os
import logging

logger = logging.getLogger(__name__)


def extract_audio(video_path: str, output_audio_path: str, sample_rate: int = 16000) -> str:
    """
    Extracts the audio track from the given video file using FFmpeg.
    """
    logger.info(f"Audio: Extracting from {video_path}...")
    try:
        (
            ffmpeg
            .input(video_path)
            .output(output_audio_path, acodec='pcm_s16le', ac=1, ar=str(sample_rate))
            .overwrite_output()
            .run(quiet=True)
        )
        logger.info(f"Audio: Extracted to {output_audio_path}")
        return output_audio_path
    except ffmpeg.Error as e:
        logger.error(f"Audio: FFmpeg error during extraction: {e.stderr.decode() if e.stderr else e}")
        raise

def analyze_audio_spikes(audio_path: str, threshold_percentile: float = 95.0) -> list:
    """
    Analyzes the audio file for sudden energy/volume spikes (RoIs).
    Returns a list of candidate regions with start, end, and energy.
    """
    logger.info(f"Audio: Analyzing {audio_path} for spikes (threshold={threshold_percentile}%)...")
    
    y, sr = librosa.load(audio_path, sr=None)
    rms = librosa.feature.rms(y=y)[0]
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sr)
    threshold = np.percentile(rms, threshold_percentile)
    spike_indices = np.where(rms > threshold)[0]

    events = []
    current_event = []
    for idx in spike_indices:
        if not current_event:
            current_event.append(idx)
        elif idx - current_event[-1] < 15:
            current_event.append(idx)
        else:
            events.append(current_event)
            current_event = [idx]
    if current_event:
        events.append(current_event)

    rois = []
    for event in events:
        start_time = float(times[event[0]])
        end_time = float(times[event[-1]])
        energy = float(np.mean(rms[event]))
        rois.append({"start": start_time, "end": end_time, "energy": energy})

    logger.info(f"Audio: Detected {len(rois)} potential audio spike events.")
    return rois


def merge_nearby_rois(rois, max_gap: float = 3.0, padding: float = 5.0) -> list:
    """
    Merges Regions of Interest that are close to each other.
    Adds padding to give context to the clip.
    """
    if not rois:
        return []

    rois.sort(key=lambda item: item["start"])
    merged = []
    current = {"start": max(0.0, rois[0]["start"] - padding), "end": rois[0]["end"] + padding, "energy": rois[0]["energy"]}

    for roi in rois[1:]:
        padded_start = max(0.0, roi["start"] - padding)
        padded_end = roi["end"] + padding
        if padded_start <= current["end"] + max_gap:
            current["end"] = max(current["end"], padded_end)
            current["energy"] = max(current["energy"], roi["energy"])
        else:
            merged.append(current)
            current = {"start": padded_start, "end": padded_end, "energy": roi["energy"]}

    merged.append(current)
    return merged
