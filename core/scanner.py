import librosa
import numpy as np
from faster_whisper import WhisperModel
import ffmpeg
import os
import gc
import torch

def extract_temp_audio(video_path: str, temp_audio_path: str):
    """Extracts a 16kHz mono audio track for ML processing."""
    try:
        (
            ffmpeg
            .input(video_path)
            .output(temp_audio_path, acodec='pcm_s16le', ac=1, ar='16000')
            .overwrite_output()
            .run(quiet=True, capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg.Error as e:
        print(f"FFmpeg Error: {e.stderr.decode() if e.stderr else str(e)}")

def run_scanner(video_path: str, db_threshold: float, hype_keywords: list, ui_callback):
    """
    Stage 1: The Ear.
    Identifies audio energy peaks and transcribes VOD for hype keywords.
    """
    ui_callback("Scanner: Extracting audio for analysis...")
    temp_dir = "temp"
    os.makedirs(temp_dir, exist_ok=True)
    temp_audio = os.path.join(temp_dir, "scanner_audio.wav")
    extract_temp_audio(video_path, temp_audio)
    
    # 1. Librosa dB Peak Detection
    ui_callback(f"Scanner: Detecting audio peaks (Threshold: {db_threshold} dB)...")
    y, sr = librosa.load(temp_audio, sr=None)
    
    # Convert to decibels
    S = np.abs(librosa.stft(y))
    db = librosa.amplitude_to_db(S, ref=np.max)
    # Average dB across frequencies for each frame
    db_per_frame = np.mean(db, axis=0)
    times = librosa.frames_to_time(np.arange(len(db_per_frame)), sr=sr, hop_length=512)
    
    peak_times = times[db_per_frame > db_threshold]
    
    ui_callback(f"Scanner: Found {len(peak_times)} raw audio spikes.")
    
    # 2. Whisper Keyword Detection
    ui_callback("Scanner: Transcribing VOD for hype keywords...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"
    
    model = WhisperModel("base", device=device, compute_type=compute_type)
    segments, _ = model.transcribe(temp_audio, word_timestamps=True)
    
    keyword_times = []
    for seg in segments:
        for word in seg.words:
            clean_word = word.word.lower().strip(" \t\n\r.,!?\"'")
            if any(kw in clean_word for kw in hype_keywords):
                keyword_times.append(word.start)
                
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    gc.collect()
    
    ui_callback(f"Scanner: Found {len(keyword_times)} hype keywords.")
    
    # 3. Merge & Deduplicate (5s window)
    all_timestamps = sorted(list(peak_times) + keyword_times)
    final_timestamps = []
    
    if all_timestamps:
        last_t = -10.0
        for t in all_timestamps:
            if t - last_t >= 5.0:
                final_timestamps.append(t)
                last_t = t
                
    if os.path.exists(temp_audio):
        os.remove(temp_audio)
        
    ui_callback(f"Scanner: Finalized {len(final_timestamps)} candidate clips.")
    return final_timestamps
