import torch
import psutil
import gc
import logging

def get_system_profile(config_overrides: dict):
    """
    Profiles the system RAM and GPU VRAM to select the best model sizes.
    """
    profile = {
        "device": "cpu",
        "whisper_model": "base",
        "compute_type": "int8"
    }
    
    if config_overrides.get("force_cpu", False):
        logging.info("Hardware Profiler: CPU forced via config.")
        return profile
        
    if torch.cuda.is_available():
        profile["device"] = "cuda"
        
        # Get total VRAM in GB
        vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        logging.info(f"Hardware Profiler: Detected CUDA GPU with {vram_gb:.2f} GB VRAM.")
        
        if vram_gb >= 11.5:
            # High-end GPU
            profile["whisper_model"] = "large-v3"
            profile["compute_type"] = "float16"
        elif vram_gb >= 6.0:
            # Mid-range GPU
            profile["whisper_model"] = "small"
            profile["compute_type"] = "float16"
        else:
            # Low-end GPU
            profile["whisper_model"] = "base"
            profile["compute_type"] = "int8"
            
    else:
        logging.info("Hardware Profiler: No CUDA GPU detected, falling back to CPU.")
        
    # Override if specified in config
    if config_overrides.get("whisper_model"):
        profile["whisper_model"] = config_overrides["whisper_model"]
        
    logging.info(f"Hardware Profiler Selected: Device={profile['device']}, Whisper={profile['whisper_model']}")
    return profile

def vram_flash():
    """
    Strict VRAM Management Protocol to force garbage collection and empty CUDA cache.
    Call this after every heavy model is used and deleted.
    """
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()
