"""
KREATOR KLIP - Main Application Entry Point
Flet 0.84.0 compatible.
"""
import os
import sys
import logging
import traceback
import json
import asyncio
import subprocess
import threading
from typing import Callable, List, Dict, Optional, Any
from dataclasses import dataclass

# Initialize logging immediately
os.makedirs("logs", exist_ok=True)

# Create formatters
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Session log (DEBUG level for all logs)
session_handler = logging.FileHandler("logs/session_log.txt", mode="w", encoding="utf-8")
session_handler.setLevel(logging.DEBUG)
session_handler.setFormatter(formatter)

# Error log (ERROR level only, appends for history)
error_handler = logging.FileHandler("logs/error_log.txt", mode="a", encoding="utf-8")
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(formatter)

# Console log (INFO level)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

# Root logger configuration
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(session_handler)
root_logger.addHandler(error_handler)
root_logger.addHandler(console_handler)

logger = logging.getLogger("KREATOR_KLIP")
logger.info("="*80)
logger.info("KREATOR KLIP - Main script started")
logger.info("="*80)

try:
    import flet as ft
    import flet_video as fv
    from flet import Icons as icons
    from flet import (
        Page, ProgressBar, Text, ListView, NavigationRail, Container, Row, Column,
        Divider, Button, ButtonStyle,
        RoundedRectangleBorder, AlertDialog, TextButton,
        GridView, Card, Icon, TextField, SnackBar, NavigationRailLabelType,
        NavigationRailDestination, VerticalDivider, ThemeMode,
        Stack, CircleAvatar
    )
    logger.info("Flet imports OK")
except Exception as e:
    logger.critical(f"Flet import failure: {e}")
    traceback.print_exc()
    sys.exit(1)

# Lazy load engine
_engine_module = None

def _get_engine():
    global _engine_module
    if _engine_module is None:
        logger.info("Lazy-loading ML engine...")
        from engine import execute_ml_pipeline_async, AssemblyLineEngine, TriggerPacket
        _engine_module = {
            "execute_ml_pipeline_async": execute_ml_pipeline_async,
            "AssemblyLineEngine": AssemblyLineEngine,
            "TriggerPacket": TriggerPacket,
        }
        logger.info("ML engine loaded OK")
    return _engine_module


def show_snack(page: Page, message: str, color=None):
    """Thread-safe snackbar using overlay (page.snack_bar removed in 0.84.0)."""
    try:
        sb = SnackBar(content=Text(message, color=ft.Colors.WHITE))
        if color:
            sb.bgcolor = color
        page.overlay.append(sb)
        sb.open = True
        page.update()
    except Exception as ex:
        logger.warning(f"Snackbar error: {ex}")


class AppState:
    def __init__(self):
        self.is_processing = False
        self.config = {}
        self.task_queue: list = []
        self.load_config()

    def load_config(self):
        try:
            with open("config.json", "r") as f:
                self.config = json.load(f)
            logger.info("Config loaded OK")
        except Exception as e:
            logger.error(f"Failed to load config.json: {e}")
            self.config = {"current_game": "valorant", "game_profiles": {}}

    def save_config(self):
        with open("config.json", "w") as f:
            json.dump(self.config, f, indent=2)


class TaskCard(Container):
    def __init__(self, packet, on_progress: Callable[[int, float], None]):
        super().__init__(padding=15, width=320, height=140)
        status_colors = {
            "QUEUED": ft.Colors.GREY_600, "PROCESSING": ft.Colors.AMBER_700,
            "COMPLETED": ft.Colors.GREEN_600, "FAILED": ft.Colors.RED_600,
        }
        status_icons_map = {
            "QUEUED": icons.SCHEDULE, "PROCESSING": icons.CONSTRUCTION,
            "COMPLETED": icons.CHECK_CIRCLE, "FAILED": icons.ERROR,
        }
        status_labels = {
            "QUEUED": "Queued", "PROCESSING": "Processing",
            "COMPLETED": "Completed", "FAILED": "Failed",
        }
        color = status_colors.get(packet.status, ft.Colors.GREY_600)
        trigger_type = "ACE Detected" if packet.is_ace else "Audio Spike"

        content_col = Column([
            Row([
                Icon(status_icons_map.get(packet.status, icons.SCHEDULE), size=24, color=color),
                Column([
                    Text(f"#{packet.clip_id}", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    Text(f"{packet.progress * 100:.0f}%", size=10, color=ft.Colors.GREY_500),
                ], spacing=2),
            ], spacing=8),
            Container(height=1, width=60, bgcolor=ft.Colors.GREY_700),
            Container(
                content=Row([
                    Icon(icons.MIC_OUTLINED if not packet.is_ace else icons.LOCAL_FIRE_DEPARTMENT,
                         size=12, color=ft.Colors.CYAN_400),
                    Text(trigger_type, size=10, weight=ft.FontWeight.W_500),
                ], spacing=5),
                padding=ft.Padding.only(left=8, right=8, bottom=8, top=8),
                bgcolor=ft.Colors.BLUE_900, border_radius=4,
            ),
            ProgressBar(value=packet.progress, color=color, height=6, border_radius=3),
            Text(status_labels.get(packet.status, "Unknown"), size=11,
                 weight=ft.FontWeight.W_500, color=color),
        ], alignment=ft.MainAxisAlignment.START, spacing=6)

        if packet.status == "FAILED" and packet.error_message:
            msg = packet.error_message[:50] + "..." if len(packet.error_message) > 50 else packet.error_message
            content_col.controls.append(Text(msg, size=9, color=ft.Colors.RED_300))

        self.content = content_col
        self.expand = True


async def run_pipeline(page: Page, vod_path: str,
                       terminal: ListView, task_list: ListView,
                       analysis_bar: ProgressBar, processing_bar: ProgressBar,
                       config: dict, state: AppState):
    if state.is_processing:
        show_snack(page, "Already processing...", ft.Colors.RED_700)
        return

    if not vod_path:
        show_snack(page, "No file selected", ft.Colors.RED_700)
        return

    vod_path = vod_path.strip().strip('"').strip("'")
    if not os.path.exists(vod_path):
        show_snack(page, "Invalid file path. Please paste a valid MP4/MKV path.", ft.Colors.RED_700)
        return

    state.is_processing = True
    analysis_bar.value = 0
    processing_bar.value = 0
    task_list.controls.clear()
    terminal.controls.clear()
    terminal.controls.append(Text(f"[INFO] Processing: {os.path.basename(vod_path)}",
                                  color=ft.Colors.CYAN_300, size=13))
    page.update()

    def processing_progress_callback(clip_id: int, percentage: float):
        try:
            for packet in state.task_queue:
                if packet.clip_id == clip_id:
                    packet.progress = percentage / 100.0
                    packet.status = "PROCESSING" if packet.progress < 1.0 else "COMPLETED"
            processing_bar.value = max([p.progress for p in state.task_queue]) if state.task_queue else 0
            page.update()
        except Exception:
            pass

    def analysis_progress(value: float):
        try:
            analysis_bar.value = min(max(value, 0.0), 1.0)
            page.update()
        except Exception:
            pass

    def log_callback(message: str, level: str = "INFO"):
        color_map = {
            "INFO": ft.Colors.CYAN_300, "WARN": ft.Colors.YELLOW_300,
            "ERROR": ft.Colors.RED_400, "SUCCESS": ft.Colors.GREEN_400,
        }
        try:
            terminal.controls.append(Text(message, color=color_map.get(level, ft.Colors.GREY_300), size=12))
            page.update()
        except Exception:
            pass

    try:
        log_callback("Loading ML engine (first run may take 10-15 sec)...", "INFO")
        engine = _get_engine()

        # Clear stale session data
        if os.path.exists("session_state.json"):
            try:
                os.remove("session_state.json")
            except Exception:
                pass

        summary, packets = await engine["execute_ml_pipeline_async"](
            vod_path, config,
            analysis_progress, processing_progress_callback, log_callback,
        )
        state.task_queue = packets
        task_list.controls.clear()
        for packet in state.task_queue:
            task_list.controls.append(TaskCard(packet, lambda *_: None))

        success_rate = (summary.completed / summary.total * 100) if summary.total else 0
        terminal.controls.append(Text(
            f"[COMPLETE] {summary.completed}/{summary.total} clips ({success_rate:.1f}% success)",
            color=ft.Colors.GREEN_400 if summary.failed == 0 else ft.Colors.YELLOW_400,
            size=13,
        ))
    except Exception as ex:
        logger.error(f"Pipeline error: {ex}\n{traceback.format_exc()}")
        terminal.controls.append(Text(f"[ERROR] {str(ex)}", color=ft.Colors.RED_400))
    finally:
        state.is_processing = False
        page.update()


def main(page: Page):
    try:
        state = AppState()
    except Exception as e:
        logger.critical(f"AppState init failed: {e}")
        page.add(Text(f"STARTUP ERROR: {e}", color=ft.Colors.RED_400))
        return

    page.title = "KREATOR KLIP | Parallel Assembly Line"
    page.theme_mode = ThemeMode.DARK
    page.padding = 0

    # Window size (compatible with both old and new Flet API)
    try:
        page.window.width = 1440
        page.window.height = 900
    except Exception:
        try:
            page.window_width = 1440
            page.window_height = 900
        except Exception:
            pass

    # UI components
    analysis_progress_bar = ProgressBar(value=0, color=ft.Colors.AMBER_400, height=6, border_radius=3)
    processing_progress_bar = ProgressBar(value=0, color=ft.Colors.CYAN_400, height=6, border_radius=3)
    terminal = ListView(expand=True, spacing=4, auto_scroll=True, padding=15)
    terminal_container = Container(content=terminal, expand=True, bgcolor=ft.Colors.BLACK26, border_radius=12)
    task_list = ListView(expand=False, spacing=10, padding=ft.Padding.only(top=10, bottom=10))

    task_list_container = Container(
        content=Column([
            Row([Icon(icons.LIST_ALT, color=ft.Colors.CYAN_200, size=16),
                 Text("LIVE TASK QUEUE", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_200)],
                spacing=8),
            task_list,
            Container(content=Text("Import a VOD to see clips here...", color=ft.Colors.GREY_500, size=11, italic=True),
                      padding=ft.Padding.only(left=25)),
        ], spacing=10),
        expand=True,
        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.BLUE),
        border_radius=12, padding=15,
    )

    vod_path_field = TextField(
        label="VOD Path", width=800,
        hint_text='Paste the full path to MP4/MKV (e.g. C:\\Videos\\gameplay.mp4)',
        autofocus=False,
    )

    async def import_vod_click(e):
        await run_pipeline(
            page, vod_path_field.value.strip(),
            terminal, task_list,
            analysis_progress_bar, processing_progress_bar,
            state.config, state,
        )

    def browse_vod_path(e):
        """Windows file picker via PowerShell — runs in background thread, no console window."""
        def _pick():
            try:
                ps_cmd = (
                    '[System.Reflection.Assembly]::LoadWithPartialName(\'System.windows.forms\') | Out-Null;'
                    '$f = New-Object System.Windows.Forms.OpenFileDialog;'
                    '$f.Filter = \'Video Files (*.mp4;*.mkv)|*.mp4;*.mkv|All Files (*.*)|*.*\';'
                    '$f.Title = \'Select VOD File\';'
                    'if ($f.ShowDialog() -eq \'OK\') { Write-Output $f.FileName }'
                )
                result = subprocess.run(
                    ["powershell", "-WindowStyle", "Hidden", "-Command", ps_cmd],
                    capture_output=True, text=True, timeout=60,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                path = result.stdout.strip()
                if path and os.path.exists(path):
                    vod_path_field.value = path
                    page.update()
            except Exception as ex:
                logger.error(f"Browse error: {ex}")

        threading.Thread(target=_pick, daemon=True).start()

    # ─── PAGES ─────────────────────────────────────────────────────────────────
    def get_scanner_page():
        return Container(
            content=Column([
                Text("VOD ANALYSIS", size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_200),
                Text("Parallel Assembly Line • RTX 3060 Optimized • GPU Throttled to 3 Concurrent Encodes",
                     color=ft.Colors.GREY_400, size=11),
                Divider(height=30),
                Row([
                    Column([
                        vod_path_field,
                        Row([
                            Button("BROWSE", icon=icons.FOLDER_OPEN, on_click=browse_vod_path,
                                   style=ButtonStyle(shape=RoundedRectangleBorder(radius=8),
                                                     padding=ft.Padding.only(top=12, bottom=12, left=24, right=24))),
                            Button("IMPORT VOD", icon=icons.VIDEO_LIBRARY, on_click=import_vod_click,
                                   style=ButtonStyle(shape=RoundedRectangleBorder(radius=8),
                                                     padding=ft.Padding.only(top=12, bottom=12, left=24, right=24))),
                        ], spacing=12),
                    ]),
                    Column([
                        Text("RTX 3060 12GB", color=ft.Colors.GREEN_400, size=11),
                        Text("CUDA 12.1 ACTIVE", color=ft.Colors.GREEN_400, size=11),
                    ], spacing=2),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                Container(
                    content=Column([
                        Icon(icons.INFO, size=48, color=ft.Colors.GREY_400),
                        Text("How to import videos:", size=16, color=ft.Colors.GREY_400, weight=ft.FontWeight.BOLD),
                        Text("1. Click BROWSE to open the file picker, or paste path directly", size=12, color=ft.Colors.GREY_500),
                        Text("2. Select your MP4/MKV file", size=12, color=ft.Colors.GREY_500),
                        Text("3. Click IMPORT VOD to start the pipeline", size=12, color=ft.Colors.GREY_500),
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
                    height=160, bgcolor=ft.Colors.BLACK12,
                    border=ft.Border.all(2, ft.Colors.GREY_700), border_radius=12,
                ),
                Container(
                    content=Column([
                        Text("ANALYSIS PROGRESS", size=11, weight=ft.FontWeight.W_500, color=ft.Colors.GREY_400),
                        analysis_progress_bar,
                        Text("PROCESSING PROGRESS", size=11, weight=ft.FontWeight.W_500, color=ft.Colors.GREY_400),
                        processing_progress_bar,
                        terminal_container,
                        task_list_container,
                    ], spacing=10),
                    expand=True, bgcolor=ft.Colors.BLACK12,
                    border_radius=12, padding=ft.Padding.only(top=15),
                ),
            ]),
            padding=30, expand=True,
        )

    def get_gallery_page(refresh=True):
        """Generate gallery page with current clips.
        If refresh=True, re-reads files from output folder.
        """
        try:
            output_dir = state.config.get("project", {}).get("output_folder",
                         state.config.get("output_folder", "output"))
            os.makedirs(output_dir, exist_ok=True)
            files = [f for f in os.listdir(output_dir) if f.endswith(".mp4")]
        except Exception as ge:
            logger.error(f"Gallery error: {ge}")
            files = []
            output_dir = "output"

        def play_video(fname):
            abs_path = os.path.abspath(os.path.join(output_dir, fname))
            try:
                video = fv.Video(playlist=[fv.VideoMedia(abs_path)], autoplay=True, aspect_ratio=9/16, expand=True)
            except Exception as ve:
                video = Text(f"Cannot play: {ve}", color=ft.Colors.RED_300)

            def close_dlg(d):
                d.open = False
                page.update()

            dlg = AlertDialog(
                content=Container(video, height=500, width=320),
                title=Text(f"PREVIEW: {fname}"),
                actions=[TextButton("CLOSE", on_click=lambda _: close_dlg(dlg))],
            )
            page.overlay.append(dlg)
            dlg.open = True
            page.update()

        if not files:
            return Container(
                content=Column([
                    Text("EXPORTED CLIPS", size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_200),
                    Text("Total: 0 clips", color=ft.Colors.GREY_400, size=11),
                    Divider(height=20),
                    Column([
                        Icon(icons.VIDEO_LIBRARY, size=64, color=ft.Colors.GREY_600),
                        Text("No clips exported yet", size=16, color=ft.Colors.GREY_500),
                        Text("Import a VOD and run the pipeline", size=12, color=ft.Colors.GREY_600),
                    ], alignment=ft.MainAxisAlignment.CENTER,
                       horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                ]),
                padding=30, expand=True,
            )

        grid = GridView(expand=True, runs_count=5, max_extent=240,
                        child_aspect_ratio=0.65, spacing=12, run_spacing=12)
        for f in sorted(files):
            grid.controls.append(
                Card(content=Container(
                    content=Column([
                        CircleAvatar(icon=icons.PLAY_CIRCLE_FILL, size=32, bgcolor=ft.Colors.CYAN_700),
                        Text(f, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS, size=11),
                        Button("VIEW", icon=icons.OPEN_IN_NEW,
                               on_click=lambda _, f=f: play_video(f),
                               style=ButtonStyle(padding=ft.Padding.only(top=4, bottom=4, left=8, right=8))),
                    ], alignment=ft.MainAxisAlignment.CENTER,
                       horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=12,
                ), color=ft.Colors.SURFACE_VARIANT)
            )

        return Container(
            content=Column([
                Text("EXPORTED CLIPS", size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_200),
                Text(f"Total: {len(files)} clips", color=ft.Colors.GREY_400, size=11),
                Divider(height=20),
                grid,
            ]),
            padding=30, expand=True,
        )

    def get_settings_page():
        try:
            config_json = json.dumps(state.config, indent=2)
        except Exception:
            config_json = "{}"

        config_text = TextField(
            value=config_json, multiline=True, expand=True,
            text_size=12, label="config.json", border_color=ft.Colors.CYAN_900,
        )

        def save_changes(e):
            try:
                state.config = json.loads(config_text.value)
                state.save_config()
                show_snack(page, "Configuration saved!", ft.Colors.GREEN_700)
            except Exception as ex:
                show_snack(page, f"Invalid JSON: {ex}", ft.Colors.RED_700)

        return Container(
            content=Column([
                Text("HARDWARE & PROFILES", size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_200),
                Text("Adjust OCR regions, hype keywords, and hardware overrides",
                     color=ft.Colors.GREY_400, size=11),
                Divider(height=20),
                config_text,
                Button("SAVE CONFIGURATION", icon=icons.SAVE_ALT, on_click=save_changes),
            ]),
            padding=30, expand=True,
        )

    # ─── NAVIGATION ────────────────────────────────────────────────────────────
    content_area = Container(expand=True)

    def switch_page(idx):
        try:
            if idx == 0:
                content_area.content = get_scanner_page()
            elif idx == 1:
                # Refresh gallery with current output folder
                content_area.content = get_gallery_page()
            elif idx == 2:
                content_area.content = get_settings_page()
            page.update()
        except Exception as ex:
            logger.error(f"Page switch error (idx={idx}): {ex}\n{traceback.format_exc()}")
    # Store gallery page function for later use
    _get_gallery = get_gallery_page
    rail = NavigationRail(
        selected_index=0,
        label_type=NavigationRailLabelType.ALL,
        min_width=90, min_extended_width=280, group_alignment=-0.85,
        destinations=[
            NavigationRailDestination(icon=icons.DASHBOARD_OUTLINED, selected_icon=icons.DASHBOARD, label="Scanner"),
            NavigationRailDestination(icon=icons.PHOTO_LIBRARY_OUTLINED, selected_icon=icons.PHOTO_LIBRARY, label="Gallery"),
            NavigationRailDestination(icon=icons.SETTINGS_OUTLINED, selected_icon=icons.SETTINGS, label="Settings"),
        ],
        on_change=lambda e: switch_page(e.control.selected_index),
    )

    content_area.content = get_scanner_page()

    page.add(Row([rail, VerticalDivider(width=1), content_area], expand=True))
    logger.info("UI rendered successfully")


if __name__ == "__main__":
    try:
        logger.info("Launching Flet app...")
        ft.run(main)
    except Exception as e:
        logger.critical(f"Flet execution failed: {e}\n{traceback.format_exc()}")
        sys.exit(1)
