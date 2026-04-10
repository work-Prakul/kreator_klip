import flet as ft
import os
import json
import asyncio
from engine import execute_ml_pipeline_async

class AppState:
    def __init__(self):
        self.is_processing = False
        self.config = {}
        self.load_config()

    def load_config(self):
        with open("config.json", "r") as f:
            self.config = json.load(f)

    def save_config(self):
        with open("config.json", "w") as f:
            json.dump(self.config, f, indent=2)

def main(page: ft.Page):
    state = AppState()
    page.title = "KREATOR KLIP | AI Gaming Clipper"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.window.width = 1280
    page.window.height = 720
    
    # --- UI COMPONENTS ---
    file_picker = ft.FilePicker()
    page.overlay.append(file_picker)
    
    # Terminal & Progress
    terminal = ft.ListView(expand=True, spacing=5, auto_scroll=True)
    progress_bar = ft.ProgressBar(value=0, color=ft.colors.CYAN_400, height=8, border_radius=5)
    
    # --- HANDLERS ---
    async def run_pipeline(e):
        if state.is_processing: return
        
        # Select VOD
        def on_result(res: ft.FilePickerResultEvent):
            if res.files:
                vod_path = res.files[0].path
                state.is_processing = True
                asyncio.run_task(execute_ml_pipeline_async(vod_path, page, terminal, progress_bar, state.config, state))
        
        file_picker.on_result = on_result
        file_picker.pick_files(allow_multiple=False, allowed_extensions=["mp4", "mkv"])

    # --- PAGES ---
    def get_scanner_page():
        return ft.Container(
            content=ft.Column([
                ft.Text("VOD ANALYSIS", size=32, weight=ft.FontWeight.BOLD, color=ft.colors.CYAN_200),
                ft.Text("AI-Driven highlight detection via audio spikes and vision confirmations", color=ft.colors.GREY_400),
                ft.Divider(height=40),
                ft.Row([
                    ft.ElevatedButton(
                        "IMPORT VOD", 
                        icon=ft.icons.VIDEO_CALL_ROUNDED, 
                        on_click=run_pipeline,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), padding=20)
                    ),
                    ft.Text("RTX 3060 12GB - CUDA 12.1 ACTIVE", color=ft.colors.GREEN_400, size=12)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Container(
                    content=terminal,
                    expand=True,
                    bgcolor=ft.colors.BLACK38,
                    border_radius=12,
                    padding=20,
                    margin=ft.margin.only(top=20)
                ),
                ft.Container(
                    content=progress_bar,
                    margin=ft.margin.only(top=10)
                )
            ]),
            padding=40,
            expand=True
        )

    def get_gallery_page():
        output_dir = state.config.get("output_folder", "output")
        os.makedirs(output_dir, exist_ok=True)
        files = [f for f in os.listdir(output_dir) if f.endswith(".mp4")]
        
        def play_video(path):
            abs_path = os.path.abspath(os.path.join(output_dir, path))
            # Flet Video player
            video = ft.Video(
                playlist=[ft.VideoMedia(abs_path)],
                autoplay=True,
                aspect_ratio=9/16,
                expand=True
            )
            dlg = ft.AlertDialog(
                content=ft.Container(video, height=600, width=340),
                title=ft.Text(f"PREVIEW: {path}"),
                actions=[ft.TextButton("CLOSE", on_click=lambda _: page.close(dlg))]
            )
            page.open(dlg)

        grid = ft.GridView(
            expand=True,
            runs_count=5,
            max_extent=250,
            child_aspect_ratio=0.6,
            spacing=15,
            run_spacing=15
        )
        
        for f in files:
            grid.controls.append(
                ft.Card(
                    content=ft.Container(
                        content=ft.Column([
                            ft.Icon(ft.icons.PLAY_CIRCLE_FILL, size=40, color=ft.colors.CYAN_200),
                            ft.Text(f, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS, size=12),
                            ft.ElevatedButton("VIEW", on_click=lambda _, f=f: play_video(f))
                        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=20
                    ),
                    color=ft.colors.SURFACE_VARIANT
                )
            )

        return ft.Container(
            content=ft.Column([
                ft.Text("EXPORTED CLIPS", size=32, weight=ft.FontWeight.BOLD, color=ft.colors.CYAN_200),
                ft.Divider(height=20),
                grid
            ]),
            padding=40,
            expand=True
        )

    def get_settings_page():
        # Simple JSON Editor for Config
        config_text = ft.TextField(
            value=json.dumps(state.config, indent=2),
            multiline=True,
            expand=True,
            text_size=13,
            label="config.json",
            border_color=ft.colors.CYAN_900
        )
        
        def save_changes(e):
            try:
                state.config = json.loads(config_text.value)
                state.save_config()
                page.snack_bar = ft.SnackBar(ft.Text("Configuration Updated!"), bgcolor=ft.colors.GREEN_700)
                page.snack_bar.open = True
                page.update()
            except Exception as ex:
                page.error(f"Invalid JSON: {ex}")

        return ft.Container(
            content=ft.Column([
                ft.Text("HARDWARE & PROFILES", size=32, weight=ft.FontWeight.BOLD, color=ft.colors.CYAN_200),
                ft.Divider(height=20),
                ft.Text("Adjust OCR regions and Hype Keywords:", color=ft.colors.GREY_400),
                config_text,
                ft.ElevatedButton("SAVE CONFIGURATION", icon=ft.icons.SAVE_ALT, on_click=save_changes)
            ]),
            padding=40,
            expand=True
        )

    # --- NAVIGATION ---
    rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=100,
        min_extended_width=400,
        group_alignment=-0.9,
        destinations=[
            ft.NavigationRailDestination(
                icon=ft.icons.DASHBOARD_OUTLINED,
                selected_icon=ft.icons.DASHBOARD,
                label="Scanner",
            ),
            ft.NavigationRailDestination(
                icon=ft.icons.PHOTO_LIBRARY_OUTLINED,
                selected_icon=ft.icons.PHOTO_LIBRARY,
                label="Gallery",
            ),
            ft.NavigationRailDestination(
                icon=ft.icons.SETTINGS_OUTLINED,
                selected_icon=ft.icons.SETTINGS,
                label="Settings",
            ),
        ],
        on_change=lambda e: switch_page(e.control.selected_index),
    )

    content_area = ft.Container(content=get_scanner_page(), expand=True)

    def switch_page(idx):
        if idx == 0: content_area.content = get_scanner_page()
        elif idx == 1: content_area.content = get_gallery_page()
        elif idx == 2: content_area.content = get_settings_page()
        page.update()

    page.add(
        ft.Row(
            [
                rail,
                ft.VerticalDivider(width=1),
                content_area,
            ],
            expand=True,
        )
    )

if __name__ == "__main__":
    ft.app(target=main)
