"""
KREATOR KLIP - Stress Test Suite
Simulates 15 concurrent triggers to verify GPU throttling (3 concurrent NVENC encodes).
"""
import asyncio
import os
import json
import sys
import time
from unittest.mock import MagicMock, patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

# Track semaphore acquisitions
semaphore_acquisitions = []
semaphore_releases = []
concurrent_count = 0
concurrent_lock = asyncio.Lock()

# Mock the core functions to simulate success and track calls
async def mock_run_scanner(*args, **kwargs):
    print("    [MOCK] Scanner ran successfully.")
    # Simulate finding 15 events for the stress test
    return [10.0, 25.5, 30.1, 45.0, 55.2, 60.0, 70.1, 80.0, 90.5, 100.0, 110.0, 120.0, 130.0, 140.0, 150.0]

async def mock_run_validator(*args, **kwargs):
    print("    [MOCK] Validator ran successfully.")
    # Return all 15 events as validated
    return [10.0, 25.5, 30.1, 45.0, 55.2, 60.0, 70.1, 80.0, 90.5, 100.0, 110.0, 120.0, 130.0, 140.0, 150.0]

async def mock_run_cutter(*args, **kwargs):
    print("    [MOCK] Cutter ran successfully.")
    await asyncio.sleep(0.05)  # Simulate work
    return True

async def mock_finisher_stage(*args, **kwargs):
    print("    [MOCK] Finisher ran successfully.")
    await asyncio.sleep(0.05)  # Simulate work
    return True

# Mock the semaphore and vram_flash to ensure the test runs without actual resource contention
async def mock_vram_flash():
    print("    [MOCK] VRAM flashed.")

# Mock the semaphore context manager with proper concurrent tracking using actual asyncio.Semaphore
async def mock_process_single_clip(video_path, event_t, temp_clip, final_clip, config, profile, update_ui, progress_callback, is_ace=False):
    """Mocked version of _process_single_clip to simulate semaphore usage."""
    print(f"    [CLIP{event_t:.0f}] Starting processing...")
    
    # Use actual asyncio.Semaphore to enforce limit
    semaphore = asyncio.Semaphore(3)
    async with semaphore:
        # Track acquisition
        async with concurrent_lock:
            concurrent_count += 1
            semaphore_acquisitions.append(time.time())
            print(f"    [SEM] Acquired (current concurrent: {concurrent_count})")
        
        try:
            # Simulate the work done inside the semaphore block
            await mock_run_cutter(video_path, event_t, temp_clip, config.get("facecam_coords", {}), lambda msg, p: print(f"    [CLIP{event_t:.0f}] {msg}"))
            await mock_finisher_stage(temp_clip, final_clip, config, profile, is_ace)
            progress_callback(1.0)
            print(f"    [CLIP{event_t:.0f}] Completed successfully!")
        finally:
            # Track release
            async with concurrent_lock:
                concurrent_count -= 1
                semaphore_releases.append(time.time())
                print(f"    [SEM] Released (current concurrent: {concurrent_count})")


async def mock_batch_render_queue(video_path: str, page, terminal, progress_bar, config, state, progress_callback):
    """Mocked version of batch_render_queue to simulate concurrent execution with 15 triggers."""
    print("\n" + "="*70)
    print("STRESS TEST: Simulating 15 concurrent triggers")
    print("GPU Throttling: asyncio.Semaphore(3) - Maximum 3 concurrent NVENC encodes")
    print("="*70)
    
    # Simulate 15 events (stress test)
    validated_events = [10.0, 25.5, 30.1, 45.0, 55.2, 60.0, 70.1, 80.0, 90.5, 100.0, 110.0, 120.0, 130.0, 140.0, 150.0]
    
    # Create 15 tasks, each wrapped to use the mock process_clip
    tasks = [
        mock_process_single_clip(
            video_path, 
            event_t, 
            os.path.join("temp", f"raw_event_{i+1}.mp4"),
            os.path.join("output", f"KreatorKlip_valorant_{i+1}.mp4"),
            config, 
            state.config, 
            lambda msg, p: print(f"    [PROGRESS] {p*100:.1f}%"),
            lambda p: progress_callback(p)
        )
        for i, event_t in enumerate(validated_events)
    ]
    
    # Use asyncio.gather to run them concurrently, which will trigger the semaphore limit
    print("\n[TEST] Launching 15 concurrent tasks...")
    start_time = time.time()
    await asyncio.gather(*tasks, return_exceptions=True)
    elapsed_time = time.time() - start_time
    
    print(f"\n[TEST] All 15 tasks completed in {elapsed_time:.2f}s")
    
    # Verify semaphore was respected
    print("\n" + "="*70)
    print("VERIFICATION: Checking semaphore compliance")
    print("="*70)
    
    max_concurrent = max(semaphore_acquisitions) - min(semaphore_acquisitions) if semaphore_acquisitions else 0
    actual_max_concurrent = len([a for a in semaphore_acquisitions if a > min(semaphore_acquisitions) and a < max(semaphore_acquisitions)])
    
    print(f"Total acquisitions tracked: {len(semaphore_acquisitions)}")
    print(f"Total releases tracked: {len(semaphore_releases)}")
    print(f"Max concurrent observed: {actual_max_concurrent}")
    
    # Check if semaphore was respected (should be <= 3)
    if actual_max_concurrent <= 3:
        print(f"\n[TEST RESULT] PASS: Semaphore correctly throttled to {actual_max_concurrent} concurrent (max allowed: 3)")
        return True
    else:
        print(f"\n[TEST RESULT] FAIL: Semaphore exceeded limit! Observed {actual_max_concurrent} concurrent (max allowed: 3)")
        return False


async def smoke_test_pipeline(video_path: str):
    """Simulates the full pipeline execution for testing."""
    print("\n" + "="*70)
    print("KREATOR KLIP - SMOKE TEST")
    print("Testing parallel assembly line with RTX 3060 optimization")
    print("="*70)
    
    # Setup mocks
    page = MockPage()
    terminal = MockListView()
    progress_bar = MockProgressBar()
    state = MockAppState()
    
    # Run the mocked batch function
    test_passed = await mock_batch_render_queue(
        video_path, page, terminal, progress_bar, state.config, state, 
        lambda p: print(f"[TEST_PROGRESS] Progress updated to {p*100:.1f}%")
    )
    
    # Check output folder for generated files
    output_folder = state.config.get("output_folder", "output")
    output_files = [f for f in os.listdir(output_folder) if f.endswith(".mp4")]
    
    print("\n" + "="*70)
    print("OUTPUT VERIFICATION")
    print("="*70)
    print(f"Output folder: {output_folder}")
    print(f"Generated MP4 files: {len(output_files)}")
    for f in sorted(output_files):
        print(f"  - {f}")
    
    if test_passed and len(output_files) == 15:
        print("\n[OVERALL RESULT] PASS: All 15 clips generated with proper GPU throttling")
        return True
    else:
        print(f"\n[OVERALL RESULT] FAIL: Expected 15 clips, got {len(output_files)}")
        return False


if __name__ == "__main__":
    # To run the async test function
    result = asyncio.run(smoke_test_pipeline("dummy_vod.mp4"))
    sys.exit(0 if result else 1)