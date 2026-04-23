# Kreator Klip Development Progress

## April 23, 2026 — Vision Gate Fix

### Bugs Identified & Fixed
- **Failure #6: Vision Gate Argument Error**: Fixed `cv2.calcOpticalFlowFarneback` signature which was failing with "Missing argument 'flow'".
- **Vision Logic Bug**: Fixed `flow.size != prev.size` comparison which was incorrectly discarding valid optical flow results.
- **Verification Logging**: Added `logger.info` to track motion scores per clip for easier debugging.

---

## April 22, 2026 — Whisper Memory Optimization

### Major Fixes for VRAM Stability
- **Hard-coded performance constraints**: Tightened `model.transcribe` parameters to prevent memory spikes (`beam_size=1`, `best_of=1`, etc.).
- **Explicit Memory Management**: Added `gc.collect()` and `torch.cuda.empty_cache()` before and after batch processing.
- **Model Downsizing**: Forced Whisper model to `"small"` to significantly reduce baseline VRAM footprint.
- **Enhanced Debug Logging**: Added per-segment progress logging.

---

## April 21, 2026 — Major Stability Session

### Bugs Identified & Fixed (10 total)

| # | Bug | File | Status |
|---|-----|------|--------|
| 1 | `main()` silently swallowed all exceptions → page never got controls → **"Working..." forever** | `main.py` | ✅ Fixed |
| 2 | `ft.FilePickerResultEvent` does not exist in Flet 0.84.0 → crash on import | `main.py` | ✅ Fixed |
| 3 | `tkinter` imported at top level conflicted with Flet window system | `main.py` | ✅ Fixed |
| 4 | `page.snack_bar` property doesn't exist in Flet 0.84.0 → crash on Settings/Gallery nav | `main.py` | ✅ Fixed |
| 5 | `ft.alignment.center` attribute doesn't exist in Flet 0.84.0 → Gallery page crash | `main.py` | ✅ Fixed |
| 6 | `PowerShell browse` spawned a visible console window → Flet opened a second app window | `main.py` | ✅ Fixed |
| 7 | `ProgressParser` used `percentage` variable before assignment | `core/render.py` | ✅ Fixed |
| 8 | Subprocess used both `universal_newlines=True` AND `text=True` (conflicting kwargs) | `core/render.py` | ✅ Fixed |
| 9 | Tried to read `process.stderr` after background thread already consumed it | `core/render.py` | ✅ Fixed |
| 10 | `TriggerPacket.to_dict()` omitted `video_path` → silent failure on session resume | `entities.py` | ✅ Fixed |

### Architecture Changes (April 21)

- **Lazy ML engine loading**: `torch`, `faster_whisper`, `librosa`, `cv2` now loaded only when IMPORT VOD is clicked. App opens instantly.
- **Immediate UI rendering**: All Flet controls are added to the page before any background work begins. "Working..." screen eliminated.
- **`show_snack()` helper**: Replaces all `page.snack_bar` calls. Uses `page.overlay` to append `SnackBar` controls (Flet 0.84.0 compatible).
- **PowerShell file browser**: Native Windows `OpenFileDialog` via PowerShell subprocess with `CREATE_NO_WINDOW` + `-WindowStyle Hidden`. No second window.
- **`switch_page()` wrapped in try/except**: Page navigation errors now log but never crash the session.
- **Stale `session_state.json` auto-deleted**: Every new IMPORT VOD run deletes any leftover session state from a previous crashed run.
- **Full config passed to validator**: Fixed config routing bug where validator received only game-specific config instead of the full config dict.

### Known Remaining Issues (April 21)

- **faster_whisper language detection on Hindi audio**: Logs show language detected as Hindi (`hi`) with low confidence (0.26–0.83) even on English gaming content. This reduces keyword matching accuracy. Workaround: set `"language": "en"` in whisper transcription config (not yet exposed in UI).
- **Vision motion gate may discard valid clips**: `motion_threshold: 0.3` on Valorant may be too strict. If no clips are returned from the pipeline, try lowering `motion_threshold` in `config.json` under `game_profiles.valorant`.
- **First-run latency**: First IMPORT VOD click takes 10–20 seconds while the ML engine (whisper model) loads for the first time. Subsequent runs are faster.

---

## April 19, 2026

- **Git Repository Cleanup**: Removed all large temp files (WAV, MP4, MKV) from git history using `git filter-branch`
- **Repository Optimization**: Reduced repository size from ~230 MB to 169 KB through aggressive garbage collection
- **Production Deployment**: Successfully pushed cleaned repository to GitHub (112 objects)
- **Comprehensive Logging**: Implemented multi-level logging system with dedicated log files
- **Error Handling**: Added automatic crash recovery with detailed logging
- **FFmpeg Integration**: Enhanced error capture and graceful failure handling
- **Hardware Detection**: Improved GPU/CPU detection with fallback mechanisms
- **UI Stability**: Fixed duplicate window issue and main window buffering problems
- **Clip Creation**: Validated end-to-end video clip creation functionality

---

## April 17, 2026

- **Fixed callback signature mismatches**: Updated `cut_video` function in `src/adapters/pipeline_gateways.py`
- **Fixed cutter module callback**: Modified `run_cutter` function in `core/cutter.py`
- **Updated UI icon reference**: Changed invalid `HOURGLASS_OUTLINED` icon to `SCHEDULE` in `main.py`
- **Enhanced configuration**: Added new keys to `config.json` for scoring weights, hardware overrides
- **Implemented hardware-adaptive architecture**: Added `utils/hardware_profile.py`
- **Added transcription batching**: Implemented batch processing for Whisper transcription
- **Implemented scoring system**: Added event ranking and weighted scoring in `core/scoring.py`
- **Disabled vision validation**: Feature flag available for future re-enablement

---

## Technical Stack

- **Core**: Python 3.11 with async pipeline orchestration
- **UI**: Flet 0.84.0 (desktop)
- **Video Processing**: FFmpeg with hardware acceleration (NVENC / h264_nvenc)
- **Transcription**: FasterWhisper with GPU acceleration and adaptive model selection
- **Audio Analysis**: Librosa for RMS spike detection
- **GPU Support**: PyTorch for CUDA detection and memory management
- **Vision Processing**: OpenCV Farneback optical flow (enabled), YOLO/EasyOCR (disabled)

---

## Current Pipeline Status

| Stage | Status | Notes |
|-------|--------|-------|
| App Launch | ✅ Working | Instant, no "Working..." hang |
| File Browser (BROWSE) | ✅ Working | Native Windows dialog via PowerShell |
| Audio Extraction (FFmpeg) | ✅ Working | Extracts to temp WAV |
| Spike Detection (Librosa) | ✅ Working | RMS threshold at 95th percentile |
| Transcription (FasterWhisper) | ✅ Running | Model loads on first use |
| Game Detection (vision.py) | ✅ Working | Fallback to config default |
| Motion Validation (OpenCV) | ⚠️ May discard too many clips | Lower `motion_threshold` if no clips appear |
| Clip Cutting (FFmpeg) | ✅ Working | GPU-accelerated (NVENC) |
| Subtitle Burn (FFmpeg + ASS) | ✅ Working | Falls back to libx264 on GPU fail |
| Gallery View | ✅ Working | Shows exported clips |
| Settings Page | ✅ Working | JSON editor with save |

---

## Log Files

| File | Purpose |
|------|---------|
| `logs/session_log.txt` | Full DEBUG-level log of the current session (overwritten each run) |
| `logs/error_log.txt` | Cumulative ERROR-level logs only (appends across sessions) |
| `session_state.json` | Transient: tracks in-progress pipeline work (auto-deleted on new run) |