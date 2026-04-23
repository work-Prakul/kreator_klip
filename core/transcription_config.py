from typing import Dict
from utils.hardware_profile import HardwareProfile


import json

def get_whisper_config(hardware_profile: HardwareProfile) -> Dict[str, object]:
    """Return Whisper compute configuration based on hardware tier."""
    whisper_lang = "hi"
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            app_config = json.load(f)
            whisper_lang = app_config.get("whisper_language", "hi")
    except Exception:
        pass

    if hardware_profile.performance_tier == "high":
        return {
            "device": "cuda",
            "compute_type": "float16",
            "model_size": "small",
            "batch_size": 8,
            "max_segment_batch": min(max(int(hardware_profile.vram_gb * 2), 1), 16),
            "language": whisper_lang
        }
    if hardware_profile.performance_tier == "mid":
        return {
            "device": "cuda",
            "compute_type": "float32",
            "model_size": "small",
            "batch_size": 4,
            "max_segment_batch": min(max(int(hardware_profile.vram_gb * 2), 1), 12),
            "language": whisper_lang
        }
    # CPU-only: use float32 (int8 quantization not reliably available on CPU)
    return {
        "device": "cpu",
        "compute_type": "float32",
        "model_size": "base",
        "batch_size": 1,
        "max_segment_batch": 2,
        "language": whisper_lang
    }
