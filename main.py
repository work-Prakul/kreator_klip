"""
KREATOR KLIP - Task-Queue UI
Live Dashboard with individual task cards showing progress, status, and triggers.
"""
from typing import Callable, List, Dict, Optional, Any

import flet as ft
import flet_video as fv  # <--- Use this for Video controls
from flet import Icons as icons
from flet import (
    Page, ProgressBar, Text, ListView, NavigationRail, Container, Row, Column,
    Divider, Button, ButtonStyle,
    RoundedRectangleBorder, AlertDialog, TextButton,
    GridView, Card, Icon, TextField, SnackBar, NavigationRailLabelType, 
    NavigationRailDestination, VerticalDivider, ThemeMode,
    Stack, CircleAvatar
)
import os
import json
import asyncio
import tkinter as tk
from tkinter import filedialog
from engine import execute_ml_pipeline_async, AssemblyLineEngine, TriggerPacket

from dataclasses import dataclass

@dataclass
class Session:
    pass


class TaskCard(Container):
    """
    Individual task card showing clip status, progress, and trigger type.
    """
    def __init__(self, packet: TriggerPacket, on_progress: Callable[[int, float], None]):
        super().__init__(padding=15, width=320, height=140)
        
        self.packet = packet
        self.on_progress = on_progress
        
        # Status colors
        self.status_colors = {
            "QUEUED": ft.Colors.GREY_600,
            "PROCESSING": ft.Colors.AMBER_700,
            "COMPLETED": ft.Colors.GREEN_600,
            "FAILED": ft.Colors.RED_600
        }
        
        # Status icons
        self.status_icons = {
            "QUEUED": icons.SCHEDULE,
            "PROCESSING": icons.CONSTRUCTION,
            "COMPLETED": icons.CHECK_CIRCLE,
            "FAILED": icons.ERROR
        }
        
        # Status labels
        self.status_labels = {
            "QUEUED": "Queued",
            "PROCESSING": "Processing",
            "COMPLETED": "Completed",
            "FAILED": "Failed"
        }
        
        # Trigger type display
        self.trigger_type = "Audio Spike"
        if packet.is_ace:
            self.trigger_type = "ACE Detected"
        
        # Build card content
        self._build_card()
    
    def _build_card(self):
        # Status indicator circle
        status_icon = Icon(
            self.status_icons.get(self.packet.status, icons.SCHEDULE),
            size=24,
            color=self.status_colors.get(self.packet.status, ft.Colors.GREY_600)
        )
        
        # Progress bar
        progress_bar = ft.ProgressBar(
            value=self.packet.progress,
            color=self.status_colors.get(self.packet.status, ft.Colors.GREY_600),
            height=6,
            border_radius=3
        )
        
        # Status text
        status_text = ft.Text(
            self.status_labels.get(self.packet.status, "Unknown"),
            size=11,
            weight=ft.FontWeight.W_500,
            color=self.status_colors.get(self.packet.status, ft.Colors.GREY_600)
        )
        
        # Progress percentage
        progress_text = Text(
            f"{self.packet.progress * 100:.0f}%",
            size=10,
            color=ft.Colors.GREY_500
        )
        
        # Trigger type badge
        trigger_badge = Container(
            content=Row([
                Icon(
                    icons.MIC_OUTLINED if not self.packet.is_ace else icons.FIRE,
                    size=12,
                    color=ft.Colors.CYAN_400
                ),
                ft.Text(
                    self.trigger_type,
                    size=10,
                    weight=ft.FontWeight.W_500
                )
            ], spacing=5),
            padding=ft.Padding.only(left=8, right=8, bottom=8, top=13),
            bgcolor=ft.Colors.BLUE_900,
            border_radius=4
        )
        
        # Clip ID
        clip_id_text = Text(
            f"#{self.packet.clip_id}",
            size=14,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.WHITE
        )
        
        # Error message (if failed)
        error_text = None
        if self.packet.status == "FAILED" and self.packet.error_message:
            error_text = Text(
                self.packet.error_message[:50] + "..." if len(self.packet.error_message) > 50 else self.packet.error_message,
                size=9,
                color=ft.Colors.RED_300
            )
        
        # Main content column
        content = Column([
            Row([
                status_icon,
                Column([
                    clip_id_text,
                    progress_text
                ], spacing=2)
            ], spacing=8),
            Container(height=1, width=60, bgcolor=ft.Colors.GREY_700),
            trigger_badge,
            progress_bar,
            status_text,
            error_text
        ], alignment=ft.MainAxisAlignment.START, spacing=6)
        
        self.content = content
        self.expand = True


class AppState:
    def __init__(self):
        self.is_processing = False
        self.config = {}
        self.task_queue: list = []
        self.load_config()

    def load_config(self):
        with open("config.json", "r") as f:
            self.config = json.load(f)

    def save_config(self):
        with open("config.json", "w") as f:
            json.dump(self.config, f, indent=2)


async def run_pipeline(page: Page, vod_path: str,
                       terminal: ListView, task_list: ListView, analysis_bar: ProgressBar,
                       processing_bar: ProgressBar, config: dict, state: AppState):
    """
    Main pipeline handler with live task queue UI.
    """
    if state.is_processing:
        page.snack_bar = SnackBar(Text("Already processing...", color=ft.Colors.RED_400))
        page.snack_bar.open = True
        page.update()
        return
    
    if not vod_path:
        page.snack_bar = SnackBar(Text("No file selected", color=ft.Colors.RED_400))
        page.snack_bar.open = True
        page.update()
        return

    # sanitize pasted path
    vod_path = vod_path.strip().strip('"').strip("'")
    if not os.path.exists(vod_path):
        page.snack_bar = SnackBar(Text("Invalid file path. Please paste a valid MP4/MKV path.", color=ft.Colors.RED_400))
        page.snack_bar.open = True
        page.update()
        return

    state.is_processing = True
    
    # Reset progress bars
    analysis_bar.value = 0
    processing_bar.value = 0
    page.update()

    # Clear previous tasks
    task_list.controls.clear()
    terminal.controls.clear()
    
    # Add header
    terminal.controls.append(ft.Text(
        f"[INFO] Processing: {os.path.basename(vod_path)}",
        color=ft.Colors.CYAN_300,
        size=13
    ))
    
    # Progress callback for processing updates
    def processing_progress_callback(clip_id: int, percentage: float):
        """Update processing progress from worker thread."""
        # Find the task packet
        for packet in state.task_queue:
            if packet.clip_id == clip_id:
                packet.progress = percentage / 100.0
                packet.status = "PROCESSING" if packet.progress < 1.0 else "COMPLETED"
        
        processing_bar.value = max([p.progress for p in state.task_queue]) if state.task_queue else 0
        page.update()

    # Analysis progress updates
    def analysis_progress(value: float):
        analysis_bar.value = min(max(value, 0.0), 1.0)
        page.update()
    
    def log_callback(message: str, level: str = "INFO"):
        color_map = {
            "INFO": ft.Colors.CYAN_300,
            "WARN": ft.Colors.YELLOW_300,
            "ERROR": ft.Colors.RED_400,
            "SUCCESS": ft.Colors.GREEN_400,
        }
        terminal.controls.append(ft.Text(message, color=color_map.get(level, ft.Colors.GREY_300), size=12))
        page.update()
    
    try:
        # Run pipeline
        summary, packets = await execute_ml_pipeline_async(
            vod_path,
            config,
            analysis_progress,
            processing_progress_callback,
            log_callback
        )
        
        state.task_queue = packets
        task_list.controls.clear()
        for packet in state.task_queue:
            card = TaskCard(packet, lambda *_: None)
            task_list.controls.append(card)
        
        success_rate = (summary.completed / summary.total * 100) if summary.total else 0
        
        terminal.controls.append(ft.Text(
            f"[COMPLETE] {summary.completed}/{summary.total} clips processed ({success_rate:.1f}% success)",
            color=ft.Colors.GREEN_400 if summary.failed == 0 else ft.Colors.YELLOW_400,
            size=13
        ))
        
    except Exception as ex:
        terminal.controls.append(ft.Text(
            f"[ERROR] {str(ex)}",
            color=ft.Colors.RED_400
        ))
        summary = type("E", (), {"total": 0, "completed": 0, "failed": 0})()
    finally:
        state.is_processing = False
        page.update()




def main(page: Page):
    try:
        state = AppState()
        page.title = "KREATOR KLIP | Parallel Assembly Line"
        page.theme_mode = ThemeMode.DARK
        page.padding = 0
        page.window.width = 1440
        page.window.height = 900
        page.window.center = True
        
        # --- UI COMPONENTS (DECLARED FIRST) ---
        # Analysis progress bar
        analysis_progress_bar = ProgressBar(
            value=0, 
            color=ft.Colors.AMBER_400, 
            height=6, 
            border_radius=3
        )
        # Processing progress bar
        processing_progress_bar = ProgressBar(
            value=0, 
            color=ft.Colors.CYAN_400, 
            height=6, 
            border_radius=3
        )
        
        # Terminal log
        terminal = ListView(
            expand=True, 
            spacing=4, 
            auto_scroll=True,
            padding=15
        )
        terminal_container = Container(
            content=terminal,
            expand=True,
            bgcolor=ft.Colors.BLACK26,
            border_radius=12,
            padding=ft.Padding.only(top=0)
        )
        
        # Task queue list
        task_list = ListView(
            expand=False,
            spacing=10,
            padding=ft.Padding.only(top=10, bottom=10)
        )
        task_list_container = Container(
            content=task_list,
            expand=True,
            bgcolor=ft.Colors.BLUE_900,
            border_radius=12,
            padding=ft.Padding.only(top=10, bottom=10)
        )
        
        # --- VOD IMPORT UI ---
        vod_path_field = TextField(
            label="VOD Path",
            width=800,
            hint_text="Paste the full path to an MP4/MKV file here (e.g., C:\\Videos\\gameplay.mp4)",
            autofocus=False
        )

        async def import_vod_click(e):
            await run_pipeline(page, vod_path_field.value.strip(), terminal, task_list, analysis_progress_bar, processing_progress_bar, state.config, state)

        def browse_vod_path(e):
            root = tk.Tk()
            root.withdraw()
            path = filedialog.askopenfilename(
                title="Select VOD File",
                filetypes=[("Video Files", "*.mp4 *.mkv")]
            )
            root.destroy()
            if path:
                vod_path_field.value = path
                page.update()

        # --- PAGES ---
        def get_scanner_page():
            return Container(
                content=Column([
                    ft.Text(
                        "VOD ANALYSIS", 
                        size=28, 
                        weight=ft.FontWeight.BOLD, 
                        color=ft.Colors.CYAN_200
                    ),
                    Text(
                        "Parallel Assembly Line • RTX 3060 Optimized • GPU Throttled to 3 Concurrent Encodes",
                        color=ft.Colors.GREY_400,
                        size=11
                    ),
                    Divider(height=30),
                    Row([
                        Column([
                            vod_path_field,
                            Row([
                                Button(
                                    "BROWSE",
                                    icon=icons.FOLDER_OPEN,
                                    on_click=browse_vod_path,
                                    style=ButtonStyle(
                                        shape=RoundedRectangleBorder(radius=8),
                                        padding=ft.Padding.only(top=12, bottom=12, left=24, right=24)
                                    )
                                ),
                                Button(
                                    "IMPORT VOD",
                                    icon=icons.VIDEO_LIBRARY,
                                    on_click=import_vod_click,
                                    style=ButtonStyle(
                                        shape=RoundedRectangleBorder(radius=8),
                                        padding=ft.Padding.only(top=12, bottom=12, left=24, right=24)
                                    )
                                )
                            ], spacing=12)
                        ]),
                        Column([
                            Text("RTX 3060 12GB", color=ft.Colors.GREEN_400, size=11),
                            Text("CUDA 12.1 ACTIVE", color=ft.Colors.GREEN_400, size=11)
                        ], spacing=2)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    Container(
                        content=Column([
                            Icon(icons.INFO, size=48, color=ft.Colors.GREY_400),
                            Text("How to import videos:", size=16, color=ft.Colors.GREY_400, weight=ft.FontWeight.BOLD),
                            Text("1. Open File Explorer and navigate to your video file", size=12, color=ft.Colors.GREY_500),
                            Text("2. Right-click the file and select 'Copy as path'", size=12, color=ft.Colors.GREY_500),
                            Text("3. Paste the path above and click IMPORT VOD", size=12, color=ft.Colors.GREY_500)
                        ], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
                        height=140,
                        bgcolor=ft.Colors.BLACK12,
                        border=ft.Border.all(2, ft.Colors.GREY_700),
                        border_radius=12
                    ),
                    Container(
                        content=Column([
                            Text(
                                "ANALYSIS PROGRESS",
                                size=11,
                                weight=ft.FontWeight.W_500,
                                color=ft.Colors.GREY_400
                            ),
                            analysis_progress_bar,
                            Text(
                                "PROCESSING PROGRESS",
                                size=11,
                                weight=ft.FontWeight.W_500,
                                color=ft.Colors.GREY_400
                            ),
                            processing_progress_bar,
                            terminal_container,
                            task_list_container
                        ], spacing=10),
                        expand=True,
                        bgcolor=ft.Colors.BLACK12,
                        border_radius=12,
                        padding=ft.Padding.only(top=15)
                    )
                ]),
                padding=30,
                expand=True
            )

        def get_gallery_page():
            output_dir = state.config.get("output_folder", "output")
            os.makedirs(output_dir, exist_ok=True)
            files = [f for f in os.listdir(output_dir) if f.endswith(".mp4")]
            
            def play_video(path):
                abs_path = os.path.abspath(os.path.join(output_dir, path))
                video = fv.Video(
                    playlist=[fv.VideoMedia(abs_path)],
                    autoplay=True,
                    aspect_ratio=9/16,
                    expand=True
                )
                dlg = AlertDialog(
                    content=Container(video, height=500, width=320),
                    title=Text(f"PREVIEW: {path}"),
                    actions=[TextButton("CLOSE", on_click=lambda _: page.close(dlg))]
                )
                page.open(dlg)
            
            grid = GridView(
                expand=True,
                runs_count=5,
                max_extent=240,
                child_aspect_ratio=0.65,
                spacing=12,
                run_spacing=12
            )
            
            for f in sorted(files):
                grid.controls.append(
                    Card(
                        content=Container(
                            content=Column([
                                CircleAvatar(
                                    icon=icons.PLAY_CIRCLE_FILL, 
                                    size=32, 
                                    bgcolor=ft.Colors.CYAN_700
                                ),
                                Text(f, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS, size=11),
                                Button(
                                    "VIEW", 
                                    icon=icons.OPEN_IN_NEW,
                                    on_click=lambda _, f=f: play_video(f),
                                    style=ButtonStyle(padding=ft.Padding.only(top=4, bottom=4, left=8, right=8))
                                )
                            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            padding=12
                        ),
                        color=ft.Colors.SURFACE_VARIANT
                    )
                )
            
            return Container(
                content=Column([
                    ft.Text(
                        "EXPORTED CLIPS", 
                        size=28, 
                        weight=ft.FontWeight.BOLD, 
                        color=ft.Colors.CYAN_200
                    ),
                    Text(
                        f"Total: {len(files)} clips",
                        color=ft.Colors.GREY_400,
                        size=11
                    ),
                    Divider(height=20),
                    grid
                ]),
                padding=30,
                expand=True
            )

        def get_settings_page():
            config_text = TextField(
                value=json.dumps(state.config, indent=2),
                multiline=True,
                expand=True,
                text_size=12,
                label="config.json",
                border_color=ft.Colors.CYAN_900
            )
            
            def save_changes(e):
                try:
                    state.config = json.loads(config_text.value)
                    state.save_config()
                    page.snack_bar = SnackBar(
                        Text("Configuration Updated!", color=ft.Colors.GREEN_400)
                    )
                    page.snack_bar.open = True
                    page.update()
                except Exception as ex:
                    page.error(f"Invalid JSON: {ex}")
            
            return Container(
                content=Column([
                    ft.Text(
                        "HARDWARE & PROFILES", 
                        size=28, 
                        weight=ft.FontWeight.BOLD, 
                        color=ft.Colors.CYAN_200
                    ),
                    Text(
                        "Adjust OCR regions, hype keywords, and hardware overrides",
                        color=ft.Colors.GREY_400,
                        size=11
                    ),
                    Divider(height=20),
                    config_text,
                    Button(
                        "SAVE CONFIGURATION", 
                        icon=icons.SAVE_ALT, 
                        on_click=save_changes
                    )
                ]),
                padding=30,
                expand=True
            )

        # --- NAVIGATION ---
        rail = NavigationRail(
            selected_index=0,
            label_type=NavigationRailLabelType.ALL,
            min_width=90,
            min_extended_width=280,
            group_alignment=-0.85,
            destinations=[
                NavigationRailDestination(
                    icon=icons.DASHBOARD_OUTLINED,
                    selected_icon=icons.DASHBOARD,
                    label="Scanner",
                ),
                NavigationRailDestination(
                    icon=icons.PHOTO_LIBRARY_OUTLINED,
                    selected_icon=icons.PHOTO_LIBRARY,
                    label="Gallery",
                ),
                NavigationRailDestination(
                    icon=icons.SETTINGS_OUTLINED,
                    selected_icon=icons.SETTINGS,
                    label="Settings",
                ),
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

        page.add(
            Row(
                [
                    rail,
                    VerticalDivider(width=1),
                    content_area,
                ],
                expand=True,
            )
        )
    except Exception as e:
        import traceback
        print(traceback.format_exc())



if __name__ == "__main__":
    ft.run(main)
