import asyncio
from typing import Callable, Dict, Any
from src.adapters.pipeline_gateways import finish_clip, cut_video


class RenderService:
    def __init__(self):
        pass

    async def cut_and_finish(
        self,
        video_path: str,
        event_time: float,
        output_clip: str,
        final_clip: str,
        config: Dict[str, Any],
        profile: Dict[str, Any],
        ui_callback: Callable[[str, str], None]
    ) -> bool:
        await asyncio.to_thread(cut_video, video_path, event_time, output_clip, config.get("facecam_coords", {}), lambda msg: ui_callback(msg, "INFO"))
        return await asyncio.to_thread(finish_clip, output_clip, final_clip, config, profile)
