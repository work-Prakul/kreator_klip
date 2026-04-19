from typing import Callable, Dict, Any
from core.scanner import run_scanner
from core.validator import run_validator
from core.cutter import run_cutter_stage
from core.transcription import run_finisher_stage
from utils.hardware import get_system_profile, vram_flash


def scan_video(video_path: str, config: Dict[str, Any], ui_callback: Callable[[str, str], None]) -> Dict[str, Any]:
    """Scanner gateway."""
    return run_scanner(video_path, config, lambda msg: ui_callback(msg, "INFO"))


def validate_video(video_path: str, events: list, game_config: dict, ui_callback: Callable[[str, str], None]) -> list:
    """Validator gateway."""
    from core.vision import run_validator_stage
    return run_validator_stage(video_path, events, game_config)


def cut_video(video_path: str, event_data: Dict[str, Any], output_path: str, config: Dict[str, Any], ui_callback: Callable[[str, str], None]) -> bool:
    """Cutter gateway."""
    event_time = event_data.get("start") if isinstance(event_data, dict) else event_data
    def progress_wrapper(clip_id: int, percentage: float):
        pass
    run_cutter_stage(video_path, event_time, output_path, config, progress_wrapper)
    return True


def finish_clip(trimmed_clip_path: str, final_output_path: str, config: Dict[str, Any], profile: Dict[str, Any]) -> bool:
    """Finisher gateway."""
    return run_finisher_stage(trimmed_clip_path, final_output_path, config, profile)


def profile_system(config_overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Hardware profiling gateway."""
    return get_system_profile(config_overrides)


def clear_gpu_cache() -> None:
    """GPU cache cleanup gateway."""
    vram_flash()
