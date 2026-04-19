import asyncio
from typing import Callable, Dict, Any, List
from src.adapters.pipeline_gateways import scan_video


class ScanService:
    def __init__(self):
        pass

    async def scan(self, video_path: str, config: Dict[str, Any], ui_callback: Callable[[str, str], None]) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(scan_video, video_path, config, ui_callback)
