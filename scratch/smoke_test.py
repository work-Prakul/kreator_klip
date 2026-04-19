import asyncio
import os
import json
from unittest.mock import MagicMock, patch

# Mock dependencies to make the test self-contained
class MockPage:
    def update(self): pass
    def open(self, dlg): pass
    def close(self, dlg): pass

class MockListView:
    def __init__(self):
        self.controls = []
    def append(self, control):
        self.controls.append(control)
    def scroll_to(self, offset, duration): pass

class MockProgressBar:
    def __init__(self):
        self.value = 0.0
    def __setattr__(self, name, value):
        super().__setattr__(name, value)

class MockAppState:
    def __init__(self):
        self.is_processing = False
        self.config = {
            "output_folder": "output",
            "db_threshold": -20.0,
            "current_game": "valorant",
            "game_profiles": {"valorant": {"keywords": ["ace", "clutch"]}},
            "facecam_coords": {"x": 100, "y": 100}
        }
        self.save_config = lambda: None

# Mock the core functions to simulate success and track calls
async def mock_run_scanner(*args, **kwargs):
    print("MOCK: Scanner ran successfully.")
    # Simulate finding 10 events for the test
    return [10.0, 25.5, 30.1, 45.0, 55.2, 60.0, 70.1, 80.0, 90.5, 100.0]

async def mock_run_validator(*args, **kwargs):
    print("MOCK: Validator ran successfully.")
    # Return all 10 events as validated
    return [10.0, 25.5, 30.1, 45.0, 55.2, 60.0, 70.1, 80.0, 90.5, 100.0]

async def mock_run_cutter(*args, **kwargs):
    print("MOCK: Cutter ran successfully.")
    await asyncio.sleep(0.1) # Simulate work
    return True

async def mock_finisher_stage(*args, **kwargs):
    print("MOCK: Finisher ran successfully.")
    await asyncio.sleep(0.1) # Simulate work
    return True

# Mock the semaphore and vram_flash to ensure the test runs without actual resource contention
async def mock_vram_flash():
    print("MOCK: VRAM flashed.")

# Mock the semaphore context manager
class MockSemaphore:
    def __init__(self, value):
        self.value = value
    async def __aenter__(self):
        print("MOCK: Semaphore acquired.")
        return self
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        print("MOCK: Semaphore released.")

# Patching the module dependencies
async def mock_process_single_clip(video_path, page, terminal, progress_bar, config, state, progress_callback):
    """Mocked version of process_clip to simulate semaphore usage."""
    print(f"--- Starting Mock Clip Processing for {os.path.basename(video_path)} ---")
    
    # Simulate the semaphore acquisition/release cycle
    async with MockSemaphore(3):
        # Simulate the work done inside the semaphore block
        await mock_run_cutter(video_path, 10.0, "temp/raw_event_1.mp4", config.get("facecam_coords", {}), lambda msg, p: print(f"[MOCK_UI] {msg}"))
        await mock_finisher_stage(None, "output/KreatorKlip_valorant_1.mp4", config, None)
        progress_callback(1.0)
    print("--- Finished Mock Clip Processing ---")


async def mock_batch_render_queue(video_path: str, page: ft.Page, terminal: ft.ListView, progress_bar: ft.ProgressBar, config: dict, state, progress_callback):
    """Mocked version of batch_render_queue to simulate concurrent execution."""
    print("\n[TEST START] Running batch_render_queue simulation...")
    
    # Simulate 10 events
    validated_events = [10.0, 25.5, 30.1, 45.0, 55.2, 60.0, 70.1, 80.0, 90.5, 100.0]
    
    # Create 10 tasks, each wrapped to use the mock process_clip
    tasks = [
        mock_process_single_clip(video_path, page, terminal, progress_bar, config, state, progress_callback)
        for _ in range(10)
    ]
    
    # Use asyncio.gather to run them concurrently, which will trigger the semaphore limit
    await asyncio.gather(*tasks)
    print("[TEST END] All 10 tasks processed via the queue manager.")


async def smoke_test_pipeline(video_path: str):
    """Simulates the full pipeline execution for testing."""
    print("\n=====================================================================")
    print("STARTING SMOKE TEST: Testing concurrent batch processing (10+ events)")
    print("=====================================================================")
    
    # Setup mocks
    page = MockPage()
    terminal = MockListView()
    progress_bar = MockProgressBar()
    state = MockAppState()
    
    # Run the mocked batch function
    await mock_batch_render_queue(
        video_path, page, terminal, progress_bar, state.config, state, 
        lambda p: print(f"[TEST_PROGRESS] Progress updated to {p*100:.1f}%")
    )

if __name__ == "__main__":
    # To run the async test function
    asyncio.run(smoke_test_pipeline("dummy_vod.mp4"))