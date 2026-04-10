import ffmpeg
import librosa
import numpy as np
import os

def extract_audio(video_path: str, output_audio_path: str, sample_rate: int = 16000) -> str:
    """
    Extracts the audio track from the given video file using FFmpeg.
    """
    print(f"Extracting audio from {video_path}...")
    try:
        (
            ffmpeg
            .input(video_path)
            .output(output_audio_path, acodec='pcm_s16le', ac=1, ar=str(sample_rate))
            .overwrite_output()
            .run(quiet=True)
        )
        print(f"Audio extracted to {output_audio_path}")
        return output_audio_path
    except ffmpeg.Error as e:
        print(f"FFmpeg error during audio extraction: {e.stderr.decode() if e.stderr else e}")
        raise

def analyze_audio_spikes(audio_path: str, threshold_percentile: float = 95.0):
    """
    Analyzes the audio file for sudden energy/volume spikes (RoIs).
    Returns a list of timestamps (in seconds) where spikes occur.
    """
    print("Analyzing audio for spikes...")
    # Load audio with librosa
    y, sr = librosa.load(audio_path, sr=None)
    
    # Calculate Root Mean Square (RMS) energy
    rms = librosa.feature.rms(y=y)[0]
    
    # Convert frames to time
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sr)
    
    # Define a dynamic threshold based on the percentile
    threshold = np.percentile(rms, threshold_percentile)
    
    # Find indices where energy exceeds the threshold
    spike_indices = np.where(rms > threshold)[0]
    
    # Group continuous spikes into distinct events (Regions of Interest)
    events = []
    current_event = []
    
    for idx in spike_indices:
        if not current_event:
            current_event.append(idx)
        else:
            # If the current index is close to the last one (e.g., within ~0.5s), lump them together
            # librosa default hop length is 512, sr=16000 -> 512/16000 = 0.032s per frame.
            # Let's say within 15 frames (~0.5s)
            if idx - current_event[-1] < 15:
                current_event.append(idx)
            else:
                events.append(current_event)
                current_event = [idx]
    if current_event:
        events.append(current_event)
        
    rois = []
    for event in events:
        start_time = times[event[0]]
        end_time = times[event[-1]]
        # Store as (start_time, end_time) tuple
        rois.append((start_time, end_time))
        
    print(f"Detected {len(rois)} potential audio spike events.")
    return rois

def merge_nearby_rois(rois, max_gap: float = 3.0, padding: float = 5.0):
    """
    Merges Regions of Interest that are close to each other.
    Adds padding to give context to the clip (e.g., 5 seconds before/after the spike).
    """
    if not rois:
        return []
        
    # Sort just in case
    rois.sort(key=lambda x: x[0])
    
    merged = []
    # Initialize with the first padded ROI
    current_start = max(0, rois[0][0] - padding)
    current_end = rois[0][1] + padding
    
    for start, end in rois[1:]:
        padded_start = max(0, start - padding)
        padded_end = end + padding
        
        # If the gap between current end and next start is small, merge
        if padded_start <= current_end + max_gap:
            current_end = max(current_end, padded_end)
        else:
            merged.append((current_start, current_end))
            current_start = padded_start
            current_end = padded_end
            
    merged.append((current_start, current_end))
    return merged
