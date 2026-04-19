"""
KREATOR KLIP - Application Entry Point
Clean Architecture UI Layer
"""
from typing import Callable, List, Dict, Any
import logging
import os
import traceback
import sys

import flet as ft
from flet import Page, ProgressBar, Text, ListView, NavigationRail, Container, Row, Column, Divider, Button, ButtonStyle, RoundedRectangleBorder, TextField, SnackBar, NavigationRailLabelType, NavigationRailDestination, VerticalDivider, ThemeMode

# Configure logging with more robust setup
os.makedirs("logs", exist_ok=True)

# Create formatters
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# File handler for all logs
file_handler = logging.FileHandler("logs/session_log.txt", mode='a', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

# File handler for errors only
error_file_handler = logging.FileHandler("logs/error_log.txt", mode='a', encoding='utf-8')
error_file_handler.setLevel(logging.ERROR)
error_file_handler.setFormatter(formatter)

# Stream handler for console
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(file_handler)
root_logger.addHandler(error_file_handler)
root_logger.addHandler(console_handler)

logger = logging.getLogger(__name__)
logger.info("="*80)
logger.info("KREATOR KLIP - Application Started")
logger.info("="*80)

from src.app.controllers import PipelineController, ConfigController
from src.app.ui.components import (
    TaskCard, FileBrowser, ProgressDisplay, TerminalLog, TaskQueue,
    VideoImportSection, InstructionsPanel, GalleryGrid, SettingsPanel
)
from src.domain.entities import TriggerPacket


class AppState:
    def __init__(self):
        self.is_processing = False
        self.config: Dict[str, Any] = {}
        self.task_queue: List[TriggerPacket] = []
        self.load_config()

    def load_config(self):
        import json
        with open("config.json", "r", encoding="utf-8") as f:
            self.config = json.load(f)

    def save_config(self):
        import json
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)


def main(page: Page):
    state = AppState()
    pipeline_controller = PipelineController(state)
    config_controller = ConfigController(state)

    page.title = "KREATOR KLIP | Parallel Assembly Line"
    page.theme_mode = ThemeMode.DARK
    page.padding = 0
    page.window.width = 1440
    page.window.height = 900

    # File Picker for overlay
    file_picker = ft.FilePicker()
    file_picker.on_result = lambda e: on_file_selected(e)
    page.overlay.append(file_picker)
    page.update()

    # UI Components
    analysis_progress_bar = ProgressBar(value=0, color=ft.Colors.AMBER_400, height=6, border_radius=3)
    processing_progress_bar = ProgressBar(value=0, color=ft.Colors.CYAN_400, height=6, border_radius=3)
    terminal = ListView(expand=True, spacing=4, auto_scroll=True, padding=15)
    task_list = ListView(expand=False, spacing=10, padding=ft.Padding.only(top=10, bottom=10))
    vod_path_field = TextField(label="VOD Path", width=800, hint_text="Paste the full path to an MP4/MKV file here (e.g., C:\\Videos\\gameplay.mp4)", autofocus=False)

    def on_file_selected(e):
        if e.files:
            vod_path_field.value = e.files[0].path
            page.update()

    # Event Handlers
    async def import_vod_click(e):
        await pipeline_controller.run_pipeline(page, vod_path_field.value, terminal, task_list, analysis_progress_bar, processing_progress_bar)

    def browse_vod_path(e):
        try:
            import asyncio
            # Fire and forget the async operation
            asyncio.create_task(file_picker.pick_files(allowed_extensions=["mp4", "mkv"]))
        except Exception as ex:
            logger.warning(f"File picker error: {ex}")

    # Page Builders
    def get_scanner_page():
        return Container(content=Column([
            Text("VOD ANALYSIS", size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_200),
            Text("Parallel Assembly Line • RTX 3060 Optimized • GPU Throttled to 3 Concurrent Encodes", color=ft.Colors.GREY_400, size=11),
            Divider(height=30),
            Row([
                VideoImportSection(vod_path_field, import_vod_click, browse_vod_path),
                Column([Text("RTX 3060 12GB", color=ft.Colors.GREEN_400, size=11), Text("CUDA 12.1 ACTIVE", color=ft.Colors.GREEN_400, size=11)], spacing=2)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            InstructionsPanel(),
            Container(content=Column([
                ProgressDisplay(analysis_progress_bar, processing_progress_bar),
                TerminalLog(terminal),
                TaskQueue(task_list)
            ], spacing=10), expand=True, bgcolor=ft.Colors.BLACK12, border_radius=12, padding=ft.Padding.only(top=15))
        ], spacing=10), padding=30, expand=True)

    def get_gallery_page():
        return Container(content=GalleryGrid(state, page), padding=30, expand=True)

    def get_settings_page():
        return Container(content=SettingsPanel(state, page), padding=30, expand=True)

    # Navigation
    rail = NavigationRail(
        selected_index=0,
        label_type=NavigationRailLabelType.ALL,
        min_width=90,
        min_extended_width=280,
        group_alignment=-0.85,
        destinations=[
            NavigationRailDestination(icon=ft.Icons.DASHBOARD_OUTLINED, selected_icon=ft.Icons.DASHBOARD, label="Scanner"),
            NavigationRailDestination(icon=ft.Icons.PHOTO_LIBRARY_OUTLINED, selected_icon=ft.Icons.PHOTO_LIBRARY, label="Gallery"),
            NavigationRailDestination(icon=ft.Icons.SETTINGS_OUTLINED, selected_icon=ft.Icons.SETTINGS, label="Settings"),
        ],
        on_change=lambda e: switch_page(e.control.selected_index),
    )

    content_area = Container(content=get_scanner_page(), expand=True)

    def switch_page(idx):
        if idx == 0:
            content_area.content = get_scanner_page()
        elif idx == 1:
            content_area.content = get_gallery_page()
        elif idx == 2:
            content_area.content = get_settings_page()
        page.update()

    page.add(Row([rail, VerticalDivider(width=1), content_area], expand=True))
