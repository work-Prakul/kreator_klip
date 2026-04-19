# Application Controllers for UI Interactions

from typing import Callable, List, Dict, Any
import os
import json
import logging
import traceback

import flet as ft
from flet import Page, ProgressBar, Text, ListView, SnackBar

from src.domain.entities import TriggerPacket
from src.use_cases.pipeline import execute_ml_pipeline_async
from src.app.ui.components import TaskCard

logger = logging.getLogger(__name__)


class PipelineController:
    """Controller for pipeline execution and UI updates."""

    def __init__(self, state):
        self.state = state

    def check_resume_session(self, page: Page) -> bool:
        """Check if there's a resumable session and prompt user."""
        if os.path.exists("session_state.json"):
            # For now, auto-resume. In production, show dialog
            return True
        return False

    async def run_pipeline(
        self,
        page: Page,
        vod_path: str,
        terminal: ListView,
        task_list: ListView,
        analysis_bar: ProgressBar,
        processing_bar: ProgressBar
    ):
        try:
            logger.info(f"Starting pipeline for: {vod_path}")
            
            if self.state.is_processing:
                logger.warning("Pipeline already processing")
                page.snack_bar = SnackBar(Text("Already processing...", color=ft.Colors.RED_400))
                page.snack_bar.open = True
                page.update()
                return

            vod_path = vod_path.strip().strip('"').strip("'")
            if not vod_path:
                logger.error("No VOD path provided")
                page.snack_bar = SnackBar(Text("No file selected", color=ft.Colors.RED_400))
                page.snack_bar.open = True
                page.update()
                return

            if not os.path.exists(vod_path):
                logger.error(f"VOD path does not exist: {vod_path}")
                page.snack_bar = SnackBar(Text("Invalid file path. Please paste a valid MP4/MKV path.", color=ft.Colors.RED_400))
                page.snack_bar.open = True
                page.update()
                return

            self.state.is_processing = True
            analysis_bar.value = 0
            processing_bar.value = 0
            page.update()

            task_list.controls.clear()
            terminal.controls.clear()
            terminal.controls.append(Text(f"[INFO] Processing: {os.path.basename(vod_path)}", color=ft.Colors.CYAN_300, size=13))
            page.update()

            def log_callback(message: str, level: str = "INFO"):
                logger.log(logging.getLevelName(level) if hasattr(logging, 'getLevelName') else logging.INFO, message)
                color_map = {
                    "INFO": ft.Colors.CYAN_300,
                    "WARN": ft.Colors.YELLOW_300,
                    "ERROR": ft.Colors.RED_400,
                    "SUCCESS": ft.Colors.GREEN_400,
                }
                terminal.controls.append(Text(message, color=color_map.get(level, ft.Colors.GREY_300), size=12))
                terminal.scroll_to(offset=-1, duration=200)
                page.update()

            def analysis_progress(value: float):
                analysis_bar.value = min(max(value, 0.0), 1.0)
                page.update()

            def processing_progress_callback(clip_id: int, percentage: float):
                for packet in self.state.task_queue:
                    if packet.clip_id == clip_id:
                        packet.progress = percentage / 100.0
                        if percentage >= 100:
                            packet.status = "COMPLETED"
                        elif percentage > 0:
                            packet.status = "PROCESSING"
                        # Update UI card
                        self._update_task_card(task_list, packet)
                # Update overall progress bar
                if self.state.task_queue:
                    processing_bar.value = sum(p.progress for p in self.state.task_queue) / len(self.state.task_queue)
                page.update()

            try:
                logger.info("Executing ML pipeline...")
                summary, packets = await execute_ml_pipeline_async(
                    vod_path,
                    self.state.config,
                    analysis_progress,
                    processing_progress_callback,
                    log_callback
                )

                self.state.task_queue = packets
                task_list.controls.clear()
                for packet in self.state.task_queue:
                    card = TaskCard(packet)
                    task_list.controls.append(card)

                success_rate = (summary.completed / summary.total * 100) if summary.total else 0
                logger.info(f"Pipeline complete: {summary.completed}/{summary.total} clips ({success_rate:.1f}% success)")
                log_callback(f"[COMPLETE] {summary.completed}/{summary.total} clips processed ({success_rate:.1f}% success)", "SUCCESS")
            except Exception as ex:
                logger.error(f"Pipeline execution failed: {ex}")
                logger.error(traceback.format_exc())
                log_callback(f"[ERROR] {str(ex)}", "ERROR")
                summary = {"total": 0, "completed": 0, "failed": 0}
        except Exception as ex:
            logger.critical(f"Pipeline controller error: {ex}")
            logger.critical(traceback.format_exc())
            page.snack_bar = SnackBar(Text(f"ERROR: {str(ex)}", color=ft.Colors.RED_400))
            page.snack_bar.open = True
        finally:
            self.state.is_processing = False
            page.update()

    def _update_task_card(self, task_list: ListView, packet: TriggerPacket):
        """Update a specific task card in the list."""
        for i, control in enumerate(task_list.controls):
            if hasattr(control, 'packet') and control.packet.clip_id == packet.clip_id:
                task_list.controls[i] = TaskCard(packet)
                break


class ConfigController:
    """Controller for configuration management."""

    def __init__(self, state):
        self.state = state

    def save_config(self, config_text: str, page: Page):
        try:
            self.state.config = json.loads(config_text)
            self.state.save_config()
            page.snack_bar = SnackBar(Text("Configuration Updated!", color=ft.Colors.GREEN_400))
            page.snack_bar.open = True
            page.update()
        except Exception as ex:
            page.error(f"Invalid JSON: {ex}")
