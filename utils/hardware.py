import torch
import psutil
import gc
import logging
from typing import Optional, Dict
from utils.hardware_profile import profile_hardware, HardwareProfile


def get_system_profile(config_overrides: Optional[Dict[str, object]] = None) -> Dict[str, object]:
    """Return a normalized hardware profile for legacy callers."""
    profile = profile_hardware(config_overrides or {})
    whisper_config = {
        "high": {"whisper_model": "large-v3", "compute_type": "float16"},
        "mid": {"whisper_model": "small", "compute_type": "float32"},
        "low": {"whisper_model": "base", "compute_type": "int8"}
    }[profile.performance_tier]

    return {
        "device": profile.device,
        "vram_gb": profile.vram_gb,
        "cpu_cores": profile.cpu_cores,
        "performance_tier": profile.performance_tier,
        "whisper_model": whisper_config["whisper_model"],
        "compute_type": whisper_config["compute_type"]
    }


def vram_flash():
    """Force a strict VRAM cleanup after heavy GPU work."""
    gc.collect()
    if torch.cuda.is_available():
        try:
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
        except Exception:
            logging.exception("Failed to flush CUDA cache")
