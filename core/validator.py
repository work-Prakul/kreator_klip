import cv2
import easyocr
import gc
import torch
import numpy as np

def extract_lookback_frames(video_path: str, event_time: float, lookback: float = 5.0, fps_sample: int = 1):
    """Extracts frames from the 5 seconds preceding an event."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened(): return []
    
    fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
    start_frame = int(max(0, event_time - lookback) * fps)
    end_frame = int(event_time * fps)
    frame_step = max(1, int(fps / fps_sample))
    
    frames = []
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    
    for fno in range(start_frame, end_frame, frame_step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, fno)
        ret, frame = cap.read()
        if not ret: break
        frames.append(frame)
        
    cap.release()
    return frames

def run_validator(video_path: str, events: list, game_config: dict, ui_callback):
    """
    Stage 2: The Eye.
    Uses EasyOCR on game-specific regions to confirm highlight events.
    """
    if not events: return []
    
    ui_callback("Validator: Initializing EasyOCR (CUDA)...")
    reader = easyocr.Reader(['en'], gpu=torch.cuda.is_available())
    locked_events = []
    
    region = game_config.get("killfeed_region", [0, 0, 0, 0]) # [y1, x1, y2, x2]
    keywords = game_config.get("keywords", ["kill", "headshot"])
    
    # Coordinates from config are [y1, x1, y2, x2]
    y1, x1, y2, x2 = region
    
    for evt in events:
        ui_callback(f"Validator: Scanning frames prior to {evt:.2f}s...")
        frames = extract_lookback_frames(video_path, evt)
        is_valid = False
        
        for frame in frames:
            h, w, _ = frame.shape
            # Ensure ROI is within bounds
            ry1, rx1 = min(h-1, y1), min(w-1, x1)
            ry2, rx2 = min(h, y2), min(w, x2)
            
            if ry2 > ry1 and rx2 > rx1:
                roi = frame[ry1:ry2, rx1:rx2]
                result = reader.readtext(roi, detail=0)
                text = " ".join(result).lower()
                
                if any(kw in text for kw in keywords):
                    is_valid = True
                    break
        
        if is_valid:
            ui_callback(f"Validator: VALIDATED highlight at {evt:.2f}s.")
            locked_events.append(evt)
        else:
            ui_callback(f"Validator: SKIPPED (No visual confirmation) at {evt:.2f}s.")
            
    del reader
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    gc.collect()
    
    ui_callback(f"Validator: Confirmed {len(locked_events)} high-quality events.")
    return locked_events
