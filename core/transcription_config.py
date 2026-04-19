from typing import Dict
from utils.hardware_profile import HardwareProfile


def get_whisper_config(hardware_profile: HardwareProfile) -> Dict[str, object]:
    """Return Whisper compute configuration based on hardware tier."""
    if hardware_profile.performance_tier == "high":
        return {
            "device": "cuda",
            "compute_type": "float16",
            "model_size": "large-v3",
            "batch_size": 8,
            "max_segment_batch": min(max(int(hardware_profile.vram_gb * 2), 1), 16)
        }
    if hardware_profile.performance_tier == "mid":
        return {
            "device": "cuda",
            "compute_type": "float32",
            "model_size": "small",
            "batch_size": 4,
            "max_segment_batch": min(max(int(hardware_profile.vram_gb * 2), 1), 12)
        }
    # CPU-only: use float32 (int8 quantization not reliably available on CPU)
    return {
        "device": "cpu",
        "compute_type": "float32",
        "model_size": "base",
        "batch_size": 1,
        "max_segment_batch": 2
    }
