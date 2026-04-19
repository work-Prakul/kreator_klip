def run_validator(video_path: str, events: list, game_config: dict, ui_callback):
    """
    Stage 2: The Eye.
    Vision validation is disabled for now to keep the pipeline stable and lightweight.
    """
    if not events:
        return []

    ui_callback("Validator: Vision validation disabled. Passing candidates through.")
    return events
