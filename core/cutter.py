from .render import run_cutter_stage


def run_cutter(video_path: str, event_data, output_path: str, config: dict, ui_callback):
    """Stage 3: The Cutter. Extract and process clip."""
    event_time = event_data.get("start") if isinstance(event_data, dict) else event_data
    def progress_wrapper(clip_id: int, percentage: float):
        pass
    return run_cutter_stage(video_path, event_time, output_path, config, progress_wrapper)
