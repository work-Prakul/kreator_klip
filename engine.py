import asyncio
import os
import torch
import gc
import flet as ft
from core.scanner import run_scanner
from core.validator import run_validator
from core.cutter import run_cutter
from core.finisher import run_finisher

async def execute_ml_pipeline_async(video_path: str, page: ft.Page, terminal: ft.ListView, progress_bar: ft.ProgressBar, config: dict, state):
    """
    The Orchestrator.
    Manages the flow from Scanner to Finisher with explicit VRAM management.
    """
    
    def update_ui(msg: str, progress: float = None):
        terminal.controls.append(ft.Text(f"[LOG] {msg}", color=ft.colors.CYAN_200))
        if progress is not None:
            progress_bar.value = progress
        page.update()
        # Scroll to bottom
        terminal.scroll_to(offset=-1, duration=200)

    update_ui(f"READY: Beginning automation sequence on {os.path.basename(video_path)}", 0.0)
    
    try:
        # --- Stage 1: SCANNER ---
        db_threshold = config.get("db_threshold", -20.0)
        current_game = config.get("current_game", "valorant")
        game_cfg = config.get("game_profiles", {}).get(current_game, {})
        hype_keywords = game_cfg.get("keywords", ["ace", "clutch"])
        
        candidates = await asyncio.to_thread(
            run_scanner, video_path, db_threshold, hype_keywords, update_ui
        )
        
        if not candidates:
            update_ui("HALT: No audio/keyword events detected. Stopping pipeline.", 1.0)
            state.is_processing = False
            page.update()
            return
            
        update_ui(f"Scanner Complete: {len(candidates)} candidates found.", 0.25)
        
        # --- VRAM Management ---
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()
        
        # --- Stage 2: VALIDATOR ---
        validated_events = await asyncio.to_thread(
            run_validator, video_path, candidates, game_cfg, update_ui
        )
        
        if not validated_events:
            update_ui("HALT: Visual verification rejected all spikes.", 1.0)
            state.is_processing = False
            page.update()
            return

        update_ui(f"Validator Complete: {len(validated_events)} events confirmed.", 0.50)

        # --- Stage 3 & 4: CUTTER & FINISHER ---
        out_folder = config.get("output_folder", "output")
        os.makedirs(out_folder, exist_ok=True)
        facecam = config.get("facecam_coords", {})
        
        step_inc = 0.50 / len(validated_events)
        current_p = 0.50
        
        for idx, event_t in enumerate(validated_events):
            update_ui(f"PRODUCING -> Clip #{idx+1} (Event at {event_t:.2f}s)...", current_p)
            
            # Temporary raw clip
            temp_clip = os.path.join("temp", f"raw_event_{idx+1}.mp4")
            final_clip = os.path.join(out_folder, f"KreatorKlip_{current_game}_{idx+1}.mp4")
            
            # Cutter (9:16 + Overlay)
            await asyncio.to_thread(run_cutter, video_path, event_t, temp_clip, facecam, update_ui)
            
            # VRAM Purge before Finisher (Large-V3)
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            gc.collect()
            
            # Finisher (Large-V3 Subtitles)
            await asyncio.to_thread(run_finisher, temp_clip, final_clip, update_ui)
            
            current_p += step_inc
            update_ui(f"Finalized Clip #{idx+1} successfully.", current_p)

        update_ui("MISSION SUCCESS! Check the Gallery page for your clips.", 1.0)
        
    except Exception as e:
        update_ui(f"SYSTEM FAULT: {str(e)}", 1.0)
        print(f"Engine Exception: {e}")
        
    state.is_processing = False
    page.update()
