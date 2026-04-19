# UI Components for the Application Layer

from typing import Callable, List, Dict, Any
import os
import json
import tkinter as tk
from tkinter import filedialog

import flet as ft
import flet_video as fv
from flet import Icons as icons
from flet import (
    Page, ProgressBar, Text, ListView, NavigationRail, Container, Row, Column,
    Divider, Button, ButtonStyle, RoundedRectangleBorder, AlertDialog, TextButton,
    GridView, Card, Icon, TextField, SnackBar, NavigationRailLabelType,
    NavigationRailDestination, VerticalDivider, ThemeMode, CircleAvatar
)

from src.domain.entities import TriggerPacket


class TaskCard(Container):
    """UI component for displaying individual task status."""

    def __init__(self, packet: TriggerPacket):
        super().__init__(padding=15, width=320, height=140)
        self.packet = packet
        self._build_card()

    def _build_card(self):
        status_colors = {
            "QUEUED": ft.Colors.GREY_600,
            "PROCESSING": ft.Colors.AMBER_700,
            "COMPLETED": ft.Colors.GREEN_600,
            "FAILED": ft.Colors.RED_600
        }
        status_icons = {
            "QUEUED": ft.Icons.HOURGLASS_EMPTY,
            "PROCESSING": ft.Icons.CONSTRUCTION,
            "COMPLETED": ft.Icons.CHECK_CIRCLE,
            "FAILED": ft.Icons.ERROR
        }
        status_labels = {
            "QUEUED": "Queued",
            "PROCESSING": "Processing",
            "COMPLETED": "Completed",
            "FAILED": "Failed"
        }

        status_icon = Icon(status_icons.get(self.packet.status, ft.Icons.HOURGLASS_EMPTY), size=24, color=status_colors.get(self.packet.status, ft.Colors.GREY_600))
        progress_bar = ft.ProgressBar(value=self.packet.progress, color=status_colors.get(self.packet.status, ft.Colors.GREY_600), height=6, border_radius=3)

        error_text = None
        if self.packet.status == "FAILED" and self.packet.error_message:
            error_text = Text(self.packet.error_message[:50] + ("..." if len(self.packet.error_message) > 50 else ""), size=9, color=ft.Colors.RED_300)

        trigger_type = "ACE Detected" if self.packet.is_ace else "Audio Spike"
        trigger_icon = ft.Icons.LOCAL_FIRE_DEPARTMENT if self.packet.is_ace else ft.Icons.MIC

        self.content = Column([
            Row([status_icon, Column([Text(f"#{self.packet.clip_id}", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE), Text(f"{self.packet.progress*100:.0f}%", size=10, color=ft.Colors.GREY_500)], spacing=2)], spacing=8),
            Divider(height=1, color=ft.Colors.GREY_700),
            Container(content=Row([Icon(trigger_icon, size=12, color=ft.Colors.CYAN_400), Text(trigger_type, size=10, weight=ft.FontWeight.W_500)], spacing=5), padding=ft.Padding.only(left=8, right=8, bottom=8, top=13), bgcolor=ft.Colors.BLUE_900, border_radius=4),
            progress_bar,
            Text(status_labels.get(self.packet.status, "Unknown"), size=11, weight=ft.FontWeight.W_500, color=status_colors.get(self.packet.status, ft.Colors.GREY_600)),
            error_text
        ], spacing=6)
        self.expand = True


class FileBrowser:
    """Utility for file selection dialogs."""

    @staticmethod
    def select_video_file() -> str:
        root = tk.Tk()
        root.withdraw()
        path = filedialog.askopenfilename(title="Select VOD File", filetypes=[("Video Files", "*.mp4 *.mkv")])
        root.destroy()
        return path or ""


class ProgressDisplay(Container):
    """UI component for progress bars."""

    def __init__(self, analysis_bar: ProgressBar, processing_bar: ProgressBar):
        super().__init__(content=Column([
            Text("ANALYSIS PROGRESS", size=11, weight=ft.FontWeight.W_500, color=ft.Colors.GREY_400),
            analysis_bar,
            Text("PROCESSING PROGRESS", size=11, weight=ft.FontWeight.W_500, color=ft.Colors.GREY_400),
            processing_bar
        ], spacing=10), expand=True, bgcolor=ft.Colors.BLACK12, border_radius=12, padding=ft.Padding.only(top=15))


class TerminalLog(Container):
    """UI component for terminal output."""

    def __init__(self, terminal: ListView):
        super().__init__(content=terminal, expand=True, bgcolor=ft.Colors.BLACK26, border_radius=12, padding=ft.Padding.only(top=0))


class TaskQueue(Container):
    """UI component for task list display."""

    def __init__(self, task_list: ListView):
        super().__init__(content=task_list, expand=True, bgcolor=ft.Colors.BLUE_900, border_radius=12, padding=ft.Padding.only(top=10, bottom=10))


class VideoImportSection(Container):
    """UI component for video import controls."""

    def __init__(self, vod_path_field: TextField, on_import: Callable, on_browse: Callable):
        super().__init__(content=Column([
            vod_path_field,
            Row([
                Button("BROWSE", icon=ft.Icons.FOLDER_OPEN, on_click=on_browse, style=ButtonStyle(shape=RoundedRectangleBorder(radius=8), padding=ft.Padding.only(top=12, bottom=12, left=24, right=24))),
                Button("IMPORT VOD", icon=ft.Icons.VIDEO_LIBRARY, on_click=on_import, style=ButtonStyle(shape=RoundedRectangleBorder(radius=8), padding=ft.Padding.only(top=12, bottom=12, left=24, right=24)))
            ], spacing=12)
        ]), expand=True)


class InstructionsPanel(Container):
    """UI component for user instructions."""

    def __init__(self):
        super().__init__(content=Column([
            Icon(ft.Icons.INFO, size=48, color=ft.Colors.GREY_400),
            Text("How to import videos:", size=16, color=ft.Colors.GREY_400, weight=ft.FontWeight.BOLD),
            Text("1. Open File Explorer and navigate to your video file", size=12, color=ft.Colors.GREY_500),
            Text("2. Right-click the file and select 'Copy as path'", size=12, color=ft.Colors.GREY_500),
            Text("3. Paste the path above and click IMPORT VOD", size=12, color=ft.Colors.GREY_500)
        ], alignment=ft.MainAxisAlignment.CENTER, spacing=8), height=140, bgcolor=ft.Colors.BLACK12, border=ft.Border.all(2, ft.Colors.GREY_700), border_radius=12)


class GalleryGrid(Container):
    """UI component for video gallery."""

    def __init__(self, state, page: Page = None):
        super().__init__()
        self.state = state
        self.page = page
        self._build_grid()

    def _build_grid(self):
        output_dir = self.state.config.get("output_folder", "output")
        os.makedirs(output_dir, exist_ok=True)
        files = [f for f in os.listdir(output_dir) if f.endswith(".mp4")]

        def play_video(path):
            if not self.page:
                return
            abs_path = os.path.abspath(os.path.join(output_dir, path))
            video = fv.Video(playlist=[fv.VideoMedia(abs_path)], autoplay=True, aspect_ratio=9/16, expand=True)
            dlg = AlertDialog(content=Container(video, height=500, width=320), title=Text(f"PREVIEW: {path}"), actions=[TextButton("CLOSE", on_click=lambda _: self.page.close(dlg))])
            self.page.open(dlg)

        grid = GridView(expand=True, runs_count=5, max_extent=240, child_aspect_ratio=0.65, spacing=12, run_spacing=12)
        for f in sorted(files):
            grid.controls.append(Card(content=Container(content=Column([
                CircleAvatar(icon=ft.Icons.PLAY_CIRCLE_FILL, size=32, bgcolor=ft.Colors.CYAN_700),
                Text(f, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS, size=11),
                Button("VIEW", icon=ft.Icons.OPEN_IN_NEW, on_click=lambda _, f=f: play_video(f), style=ButtonStyle(padding=ft.Padding.only(top=4, bottom=4, left=8, right=8)))
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER), padding=12), color=ft.Colors.SURFACE_VARIANT))

        self.content = Column([
            Text("EXPORTED CLIPS", size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_200),
            Text(f"Total: {len(files)} clips", color=ft.Colors.GREY_400, size=11),
            Divider(height=20),
            grid
        ], expand=True)


class SettingsPanel(Container):
    """UI component for settings."""

    def __init__(self, state, page: Page = None):
        super().__init__()
        self.state = state
        self.page = page
        self._build_panel()

    def _build_panel(self):
        config_text = TextField(value=json.dumps(self.state.config, indent=2), multiline=True, expand=True, text_size=12, label="config.json", border_color=ft.Colors.CYAN_900)

        def save_changes(e):
            if not self.page:
                return
            try:
                self.state.config = json.loads(config_text.value)
                self.state.save_config()
                self.page.snack_bar = SnackBar(Text("Configuration Updated!", color=ft.Colors.GREEN_400))
                self.page.snack_bar.open = True
                self.page.update()
            except Exception as ex:
                self.page.error(f"Invalid JSON: {ex}")

        self.content = Column([
            Text("HARDWARE & PROFILES", size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_200),
            Text("Adjust OCR regions, hype keywords, and hardware overrides", color=ft.Colors.GREY_400, size=11),
            Divider(height=20),
            config_text,
            Button("SAVE CONFIGURATION", icon=ft.Icons.SAVE_ALT, on_click=save_changes)
        ], expand=True)
