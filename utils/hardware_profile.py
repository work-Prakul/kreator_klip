import torch
import psutil
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class HardwareProfile:
    has_cuda: bool
    vram_gb: float
    cpu_cores: int
    performance_tier: str
    device: str


def profile_hardware(config_overrides: Optional[Dict[str, object]] = None) -> HardwareProfile:
    """Detect system hardware and classify performance tier."""
    config_overrides = config_overrides or {}
    has_cuda = False
    vram_gb = 0.0
    cpu_cores = psutil.cpu_count(logical=False) or psutil.cpu_count(logical=True) or 1

    try:
        if not config_overrides.get("force_cpu", False) and torch.cuda.is_available():
            # Verify CUDA actually works before claiming it
            try:
                torch.cuda.empty_cache()
                vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
                has_cuda = True
            except Exception:
                # CUDA available but not functional, fall back to CPU
                has_cuda = False
                vram_gb = 0.0
    except Exception:
        has_cuda = False
        vram_gb = 0.0

    if has_cuda and vram_gb >= 10.0:
        performance_tier = "high"
    elif has_cuda:
        performance_tier = "mid"
    else:
        performance_tier = "low"

    device = "cuda" if has_cuda else "cpu"

    return HardwareProfile(
        has_cuda=has_cuda,
        vram_gb=vram_gb,
        cpu_cores=cpu_cores,
        performance_tier=performance_tier,
        device=device
    )
