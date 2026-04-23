"""Lightweight motion-based visual validation using OpenCV optical flow."""

import cv2
import numpy as np
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def _sample_frames(video_path: str, timestamp: float, window_seconds: float = 10.0, fps: float = 1.0) -> List[np.ndarray]:
    """Sample frames around a candidate timestamp within a window."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.warning(f"Failed to open video: {video_path}")
        cap.release()
        return []

    start_ms = int((timestamp - window_seconds / 2.0) * 1000)
    end_ms = int((timestamp + window_seconds / 2.0) * 1000)
    cap.set(cv2.CAP_PROP_POS_MSEC, start_ms)

    frames = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        current_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
        if current_ms > end_ms:
            break
        # Resize to 320x180 for faster optical flow
        frame_small = cv2.resize(frame, (320, 180))
        gray = cv2.cvtColor(frame_small, cv2.COLOR_BGR2GRAY)
        frames.append(gray)

    cap.release()
    return frames


def _sample_initial_frames(video_path: str, num_frames: int = 3) -> List[np.ndarray]:
    """Sample initial frames from the beginning of a video for game detection."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.warning(f"Failed to open video: {video_path}")
        cap.release()
        return []

    frames = []
    for _ in range(num_frames):
        ret, frame = cap.read()
        if not ret:
            break
        # Resize to 320x180 for faster processing
        frame_small = cv2.resize(frame, (320, 180))
        frames.append(frame_small)

    cap.release()
    return frames


def _compute_ui_activity_score(frame: np.ndarray, region: List[int]) -> float:
    """Compute UI activity score in a region using color density heuristic."""
    if len(frame.shape) < 3 or frame.shape[2] != 3:
        # Convert grayscale to BGR for consistency
        frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

    x, y, w, h = region
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(frame.shape[1], x + w), min(frame.shape[0], y + h)

    roi = frame[y1:y2, x1:x2]
    if roi.size == 0:
        return 0.0

    # Sample center region for UI activity
    h_roi, w_roi, _ = roi.shape
    center_h, center_w = int(h_roi * 0.3), int(w_roi * 0.3)
    center_roi = roi[h_roi//2 - center_h//2:h_roi//2 + center_h//2,
                     w_roi//2 - center_w//2:w_roi//2 + center_w//2]

    if center_roi.size == 0:
        return 0.0

    # Compute color variance as activity metric
    gray_center = cv2.cvtColor(center_roi, cv2.COLOR_BGR2GRAY)
    activity = np.std(gray_center)
    return min(activity / 255.0, 1.0)


def identify_game_visual(video_path: str, config: Dict[str, Any]) -> str:
    """
    Identify the game by analyzing UI regions in sampled frames.

    Heuristic: Compare UI activity scores in killfeed regions across game profiles.
    Returns the detected game ID or the current_game from config if uncertain.
    """
    game_profiles = config.get("game_profiles", {})
    if not game_profiles:
        return config.get("current_game", "generic")

    try:
        frames = _sample_initial_frames(video_path, num_frames=3)
        if not frames:
            logger.warning("identify_game_visual: Could not sample frames, using default game.")
            return config.get("current_game", "generic")

        # Use first frame for analysis
        frame = frames[0]
        best_match = None
        best_score = -1

        for game_id, profile in game_profiles.items():
            region = profile.get("killfeed_region", [0, 0, 0, 0])
            if len(region) >= 4:
                score = _compute_ui_activity_score(frame, region)
                if score > best_score:
                    best_score = score
                    best_match = game_id

        # If we found a significant match, return it
        if best_score > 0.15 and best_match:
            logger.info(f"Visual Match: {best_match} detected (score={best_score:.2f}).")
            return best_match

        # Default to current_game if uncertain
        logger.info("Visual Match: No clear game detected, using configured default.")
        return config.get("current_game", "generic")

    except Exception as e:
        logger.warning(f"identify_game_visual failed: {e}, using default game.")
        return config.get("current_game", "generic")


def _resize_for_flow(frame: np.ndarray) -> np.ndarray:
    """Resize frame to 320x180 for optical flow computation."""
    h, w = frame.shape[:2]
    new_w, new_h = 320, int(180 * 320 / w)
    return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)


def motion_score(video_path: str, timestamp: float, config: Dict[str, Any]) -> float:
    """
    Compute motion score using optical flow.

    Args:
        video_path: Path to the video file
        timestamp: Candidate event timestamp in seconds
        config: Config dict with "game_profiles" containing "motion_threshold" per game

    Returns:
        Normalized motion score in [0.0, 1.0]
    """
    try:
        frames = _sample_frames(video_path, timestamp, window_seconds=10.0, fps=1.0)
        if len(frames) < 2:
            logger.warning(f"Not enough frames for motion analysis at {timestamp}")
            return 0.0

        # Compute optical flow between consecutive frame pairs
        flow_scores = []
        for i in range(len(frames) - 1):
            prev = frames[i]
            next_frame = frames[i + 1]

            # Calculate optical flow using Farneback algorithm
            flow = cv2.calcOpticalFlowFarneback(
                prev,        # pos 1: previous frame
                next_frame,  # pos 2: current frame
                None,        # pos 3: REQUIRED 'flow' argument (pass None to create new)
                0.5,         # pyr_scale
                3,           # levels
                15,          # winsize
                3,           # iterations
                5,           # poly_n
                1.2,         # poly_sigma
                0            # flags
            )

            if flow is None:
                continue

            # Compute mean magnitude
            magnitude = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
            mean_magnitude = float(np.mean(magnitude))
            logger.info(f"Vision: Clip at {timestamp} scored {mean_magnitude:.3f}")
            flow_scores.append(mean_magnitude)

        if not flow_scores:
            logger.warning(f"No valid optical flow computed for {video_path}")
            return 0.0

        # Get global vision threshold
        motion_threshold = config.get("vision", {}).get("motion_threshold", 0.12)

        # Normalize by frame diagonal for resolution consistency
        cap = cv2.VideoCapture(video_path)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_POS_MSEC, 0)
            ret, first_frame = cap.read()
            if ret and first_frame is not None:
                h, w = first_frame.shape[:2]
                diagonal = np.sqrt(w**2 + h**2)
                # Scale threshold by diagonal (pixels per frame)
                normalized_threshold = motion_threshold * (diagonal / 1080.0)
            else:
                normalized_threshold = motion_threshold
            cap.release()
        else:
            normalized_threshold = motion_threshold

        # Normalize flow magnitudes
        max_expected = normalized_threshold * 10.0  # Allow up to 10x threshold
        if max_expected <= 0:
            max_expected = 1.0

        normalized_scores = [min(mag / max_expected, 1.0) for mag in flow_scores]
        mean_score = np.mean(normalized_scores)

        return mean_score

    except Exception as e:
        logger.error(f"Motion score computation failed: {e}")
        return 0.0


_ocr_reader = None

def _get_ocr_reader(use_gpu):
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        _ocr_reader = easyocr.Reader(['en'], gpu=use_gpu)
    return _ocr_reader


def detect_player_kill(video_path, timestamp, config):
    """
    Returns True if wildflame/wildflame75 appears as KILLER
    in the killfeed at the given timestamp.
    Returns False if they appear as victim, are absent,
    or a spectator indicator is present.
    """
    try:
        if not config.get("vision", {}).get("enable_killfeed_ocr", False):
            return True

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return False

        cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            return False

        use_gpu = config.get("use_gpu", True)
        reader = _get_ocr_reader(use_gpu)

        # 4. Check for spectator indicators on the FULL frame first
        spectator_strings = config.get("vision", {}).get("spectator_strings", ["spectating", "observer"])
        full_frame_results = reader.readtext(frame)
        for _, text, conf in full_frame_results:
            if conf > 0.4:
                text_lower = text.lower()
                if any(s in text_lower for s in spectator_strings):
                    return False

        # 2. Get killfeed_region
        current_game = config.get("current_game", "generic")
        killfeed_region = config.get("game_profiles", {}).get(current_game, {}).get("killfeed_region", [0, 0, 0, 0])
        if len(killfeed_region) < 4:
            return False
            
        x1, y1, x2, y2 = killfeed_region
        if x2 <= x1 or y2 <= y1:
            return False

        killfeed_crop = frame[y1:y2, x1:x2]
        if killfeed_crop.size == 0:
            return False

        # 3. Run EasyOCR on cropped region
        results = reader.readtext(killfeed_crop)

        # 5. Find matches
        handles = config.get("vision", {}).get("player_handles", ["wildflame", "wildflame75"])
        matches = []
        for bbox, text, conf in results:
            if conf > 0.4:
                text_lower = text.lower()
                if any(h in text_lower for h in handles):
                    matches.append((bbox, text, conf))

        if not matches:
            return False

        # 6. For each match, compute center_x
        crop_midpoint = killfeed_crop.shape[1] / 2
        for match in matches:
            bbox = match[0]
            center_x = (bbox[0][0] + bbox[2][0]) / 2
            if center_x < crop_midpoint:
                return True   # killer - valid clip

        # 7. If all matches are on the right side
        return False

    except Exception as e:
        logger.error(f"detect_player_kill failed: {e}")
        return False


def validate_event(video_path: str, event: Dict[str, Any], config: Dict[str, Any]) -> bool:
    # Step 1: motion gate (existing)
    score = motion_score(video_path, event["start"], config)
    threshold = config.get("vision", {}).get("motion_threshold", 0.12)
    if score < threshold:
        logger.info(f"Discarded (low_motion): score={score:.3f}")
        return False

    # Step 2: killfeed gate (new)
    if not detect_player_kill(video_path, event["start"], config):
        logger.info(f"Discarded (no_player_kill): t={event['start']}")
        return False

    return True


def run_validator_stage(video_path: str, events: List[Dict[str, Any]], config: Dict[str, Any], game: str = "generic") -> List[Dict[str, Any]]:
    """Run vision validation on candidate events."""
    enable_heavy_vision = config.get("vision", {}).get("enable_heavy_vision", False)

    if not enable_heavy_vision:
        logger.info("Vision validator: motion-based validation enabled.")
        validated = []
        for event in events:
            if validate_event(video_path, event, config):
                validated.append(event)
            else:
                logger.info(f"Event discarded: low_motion")
        return validated

    logger.info("Vision validator: heavy vision (YOLO/EasyOCR) disabled by default.")
    return events
