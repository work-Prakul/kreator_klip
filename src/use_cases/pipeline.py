import asyncio
import os
import logging
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Callable, Tuple, AsyncGenerator

from src.domain.entities import TriggerPacket, PipelineSummary
from src.adapters.pipeline_gateways import (
    profile_system, scan_video, validate_video, cut_video, finish_clip, clear_gpu_cache
)

logger = logging.getLogger(__name__)


def estimate_max_concurrent() -> int:
    """Dynamically estimate max concurrent renders based on VRAM."""
    try:
        # For RTX 3060 12GB, assume ~2.5GB per render task
        vram_gb = 12  # Hardcoded for now; could use torch.cuda.mem_get_info()
        per_task_gb = 2.5
        max_tasks = max(1, int(vram_gb / per_task_gb))
        return min(max_tasks, 6)  # Cap at 6
    except Exception:
        return 3  # Fallback


class AssemblyLineEngine:
    """High-performance pipeline engine with async throttling."""

    def __init__(self, max_concurrent: int = None):
        if max_concurrent is None:
            max_concurrent = estimate_max_concurrent()
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.clip_packets: List[TriggerPacket] = []
        self.completed_count = 0
        self.failed_count = 0
        self.profile: Dict[str, Any] = {}
        self.current_game: str = "valorant"
        self.session_file = "session_state.json"

    def save_session_state(self):
        """Serialize current state to session_state.json."""
        state = {
            "packets": [p.to_dict() for p in self.clip_packets],
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "profile": self.profile,
            "current_game": self.current_game
        }
        with open(self.session_file, "w") as f:
            json.dump(state, f, indent=2)

    def load_session_state(self) -> bool:
        """Load state from session_state.json if exists."""
        if not os.path.exists(self.session_file):
            return False
        try:
            with open(self.session_file, "r") as f:
                state = json.load(f)
            self.clip_packets = [TriggerPacket.from_dict(p) for p in state.get("packets", [])]
            self.completed_count = state.get("completed_count", 0)
            self.failed_count = state.get("failed_count", 0)
            self.profile = state.get("profile", {})
            self.current_game = state.get("current_game", "valorant")
            return True
        except Exception as e:
            logger.error(f"Failed to load session state: {e}")
            return False

    def clear_session_state(self):
        """Remove session state file."""
        if os.path.exists(self.session_file):
            os.remove(self.session_file)

    async def scan_and_validate_stream(
        self,
        video_path: str,
        config: Dict[str, Any],
        progress_callback: Callable[[float], None],
        log_callback: Callable[[str, str], None]
    ) -> AsyncGenerator[TriggerPacket, None]:
        """Stream triggers as they are validated, enabling real-time processing."""
        logger.info("=== ASSEMBLY LINE: STREAMING SCAN PHASE ===")

        self.profile = profile_system(config.get("hardware_overrides", {}))
        logger.info(f"Hardware Confirmed: {self.profile['device']} with {self.profile.get('whisper_model', 'base')} model.")
        log_callback(f"Hardware Profiling: {self.profile['device']} / {self.profile.get('whisper_model', 'base')}", "INFO")

        # Auto-detect game from video UI regions
        from core.vision import identify_game_visual
        self.current_game = identify_game_visual(video_path, config)
        game_cfg = config.get("game_profiles", {}).get(self.current_game, {})

        log_callback(f"Game Detection: {self.current_game} identified from UI analysis.", "INFO")
        log_callback("Scanner: Extracting audio and detecting spikes...", "INFO")
        candidates = await asyncio.to_thread(scan_video, video_path, config, log_callback)

        progress_callback(0.35)
        if not candidates:
            logger.warning("HALT: No audio/keyword events detected.")
            log_callback("HALT: No audio/keyword events detected.", "WARN")
            return

        clear_gpu_cache()
        log_callback(f"Scanner complete: {len(candidates)} candidate events found.", "INFO")

        validated_events = await asyncio.to_thread(validate_video, video_path, candidates, game_cfg, log_callback)
        clear_gpu_cache()

        clip_id = 1
        for event_data in validated_events:
            packet = TriggerPacket(
                clip_id=clip_id,
                video_path=video_path,
                event_time=event_data.get("start") if isinstance(event_data, dict) else event_data,
                is_ace=False,
                status="QUEUED"
            )
            self.clip_packets.append(packet)
            self.save_session_state()
            yield packet
            clip_id += 1

        progress_callback(0.75)
        log_callback(f"Streaming validation complete: {len(self.clip_packets)} events confirmed.", "INFO")

    async def render_single_packet(
        self,
        packet: TriggerPacket,
        config: Dict[str, Any],
        progress_callback: Callable[[int, float], None],
        log_callback: Callable[[str, str], None]
    ):
        """Render a single packet with semaphore control and persistence."""
        async with self.semaphore:
            try:
                packet.status = "PROCESSING"
                self.save_session_state()
                progress_callback(packet.clip_id, 10)

                output_folder = config.get("output_folder", "output")
                os.makedirs(output_folder, exist_ok=True)

                temp_clip = os.path.join("temp", f"raw_event_{packet.clip_id}.mp4")
                final_clip = os.path.join(output_folder, f"KreatorKlip_{self.current_game}_{packet.clip_id}.mp4")

                log_callback(f"CLIP {packet.clip_id}: Cutter stage started.", "INFO")
                await asyncio.to_thread(
                    cut_video,
                    packet.video_path,
                    {"start": packet.event_time},
                    temp_clip,
                    config,
                    log_callback
                )

                progress_callback(packet.clip_id, 50)
                log_callback(f"CLIP {packet.clip_id}: Finisher stage started.", "INFO")

                await asyncio.to_thread(
                    finish_clip,
                    temp_clip,
                    final_clip,
                    config,
                    self.profile
                )

                progress_callback(packet.clip_id, 100)
                packet.status = "COMPLETED"
                packet.progress = 1.0
                self.completed_count += 1
                log_callback(f"CLIP {packet.clip_id}: COMPLETED", "SUCCESS")
                self.save_session_state()

            except Exception as e:
                packet.status = "FAILED"
                packet.error_message = str(e)
                self.failed_count += 1
                log_callback(f"CLIP {packet.clip_id} FAILED: {e}", "ERROR")
                self.save_session_state()
                clear_gpu_cache()

    def get_summary(self) -> PipelineSummary:
        return PipelineSummary(
            total=len(self.clip_packets),
            completed=self.completed_count,
            failed=self.failed_count,
            packets=[p.to_dict() for p in self.clip_packets]
        )


async def execute_ml_pipeline_async(
    video_path: str,
    config: Dict[str, Any],
    analysis_progress_callback: Callable[[float], None],
    render_progress_callback: Callable[[int, float], None],
    log_callback: Callable[[str, str], None]
) -> Tuple[PipelineSummary, List[TriggerPacket]]:
    """Execute the conveyor pipeline: scan and render concurrently."""
    engine = AssemblyLineEngine()

    # Check for resume
    if engine.load_session_state():
        log_callback("Resuming previous session...", "INFO")
        # Resume rendering incomplete packets
        pending_packets = [p for p in engine.clip_packets if p.status in ["QUEUED", "PROCESSING"]]
        if pending_packets:
            render_tasks = [
                engine.render_single_packet(p, config, render_progress_callback, log_callback)
                for p in pending_packets
            ]
            await asyncio.gather(*render_tasks, return_exceptions=True)
    else:
        # New session: stream scan and render
        render_tasks = []
        async for packet in engine.scan_and_validate_stream(video_path, config, analysis_progress_callback, log_callback):
            # Start rendering immediately
            task = asyncio.create_task(
                engine.render_single_packet(packet, config, render_progress_callback, log_callback)
            )
            render_tasks.append(task)

        # Wait for all render tasks to complete
        if render_tasks:
            await asyncio.gather(*render_tasks, return_exceptions=True)

    analysis_progress_callback(1.0)
    summary = engine.get_summary()
    log_callback(
        f"MISSION STATUS: {summary.completed}/{summary.total} clips processed ({(summary.completed / summary.total * 100) if summary.total else 0:.1f}% success)",
        "INFO"
    )

    # Clear session on completion
    engine.clear_session_state()
    return summary, engine.clip_packets


def batch_render_queue(
    video_path: str,
    config: Dict[str, Any],
    analysis_progress_callback: Callable[[float], None],
    render_progress_callback: Callable[[int, float], None],
    log_callback: Callable[[str, str], None]
):
    asyncio.create_task(execute_ml_pipeline_async(
        video_path,
        config,
        analysis_progress_callback,
        render_progress_callback,
        log_callback
    ))
