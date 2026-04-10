import cv2
import easyocr
import numpy as np
import logging
from ultralytics import YOLO
from utils.hardware import vram_flash

def extract_lookback_frames(video_path: str, event_time: float, lookback: float = 5.0, fps_sample: int = 1):
    """
    Extracts frames prior to the event timestamp to look for visual cues (e.g. killfeed).
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise Exception(f"Failed to open {video_path}")
        
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps == 0 or np.isnan(fps):
        fps = 60.0 # fallback
        
    start_time = max(0, event_time - lookback)
    end_time = event_time
    
    start_frame = int(start_time * fps)
    end_frame = int(end_time * fps)
    
    frame_step = max(1, int(fps / fps_sample))
    
    frames = []
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    current_frame = start_frame
    
    while current_frame <= end_frame:
        ret, frame = cap.read()
        if not ret:
            break
            
        timestamp = current_frame / fps
        frames.append((timestamp, frame))
        
        current_frame += frame_step
        cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
        
    cap.release()
    return frames

def run_validator_stage(video_path: str, events: list, game: str = "generic"):
    """
    Stage 2: The Validator.
    Samples 5 seconds prior to Event Timestamps. If visual confirmation is found, locks it.
    """
    logging.info("--- STAGE 2: THE VALIDATOR ---")
    
    if not events:
        logging.info("Validator: No events to validate.")
        return []
        
    logging.info("Validator: Loading OCR and YOLO models...")
    try:
        reader = easyocr.Reader(['en'], gpu=True)
        model = YOLO('yolov8n.pt') 
    except Exception as e:
        logging.error(f"Validator: Failed to load models: {e}")
        vram_flash()
        return []
        
    locked_events = []
    
    for event_t in events:
        logging.info(f"Validator: Checking Event at {event_t:.2f}s...")
        try:
            frames = extract_lookback_frames(video_path, event_t, lookback=5.0, fps_sample=1)
            event_locked = False
            
            for (t, frame) in frames:
                height, width, _ = frame.shape
                
                if game in ["valorant", "cs2"]:
                    # Targeted OCR on Killfeed
                    crop_y = int(height * 0.3)
                    crop_x = int(width * 0.7)
                    top_right = frame[0:crop_y, crop_x:width]
                    
                    result = reader.readtext(top_right)
                    text_detected = " ".join([res[1] for res in result]).lower()
                    
                    if any(kw in text_detected for kw in ["headshot", "killed", "eliminated", "assist"]):
                        event_locked = True
                        break
                else:
                    # Generic action check
                    results = model.predict(frame, verbose=False)
                    if len(results[0].boxes) >= 2: # At least 2 objects/people interacting
                        event_locked = True
                        break
                        
            if event_locked:
                logging.info(f"  -> LOCKED: Visual confirmation found.")
                locked_events.append(event_t)
            else:
                logging.info(f"  -> DROPPED: No visual match found.")
                
        except Exception as e:
            logging.error(f"Validator: Exception during frame processing for timestamp {event_t}: {e}")
            continue # Drop and move to next
            
    # Clean up Heavy Models
    del reader
    del model
    vram_flash()
    
    return locked_events
