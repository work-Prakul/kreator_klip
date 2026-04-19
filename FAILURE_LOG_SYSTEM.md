# KreatorKlip Failure Logging System

**Last Updated:** 2026-04-19  
**Status:** ✅ ACTIVE

---

## 📋 Logging Configuration

The application now has a comprehensive multi-level logging system that captures all errors and warnings:

### Log Files Created

1. **`logs/session_log.txt`** - ALL application logs
   - Level: DEBUG
   - Contains: Everything (info, warnings, errors)
   - Format: `TIMESTAMP - LOGGER - LEVEL - MESSAGE`

2. **`logs/error_log.txt`** - ERROR logs only
   - Level: ERROR
   - Contains: Only critical failures
   - Format: `TIMESTAMP - LOGGER - LEVEL - MESSAGE`

3. **`logs/runtime_output.txt`** - Console output (when redirected)
   - Level: INFO
   - Contains: Console output and errors
   - Format: Raw console output

### Logging Architecture

```python
# Configured in: src/app/main.py
# Three handlers:
# 1. FileHandler -> session_log.txt (DEBUG level)
# 2. FileHandler -> error_log.txt (ERROR level only)
# 3. StreamHandler -> Console (INFO level)
```

---

## 🔴 Failures Captured & Fixed

### Failure #1: Asyncio Event Loop Conflict
**Date:** 2026-04-15  
**Error:** `RuntimeError: asyncio.run() cannot be called from a running event loop`  
**File:** `core/scanner.py`  
**Status:** ✅ FIXED

**Solution:**
- Removed `asyncio.run()` call inside thread
- Changed to synchronous `_sync_transcribe_batch()` function
- Imported: `from core.transcription import _sync_transcribe_batch`

---

### Failure #2: Float16 Compute Type on CPU
**Date:** 2026-04-15  
**Error:** `ValueError: Requested float16 compute type, but the target device or backend do not support efficient float16 computation`  
**File:** `core/transcription_config.py`  
**Status:** ✅ FIXED

**Solution:**
- Changed CPU compute type from `int8` to `float32`
- Hardware profile now correctly returns `float32` for CPU-only systems
- Added fallback logic in `_sync_transcribe_batch`

---

### Failure #3: FilePickerResultEvent Type Error
**Date:** 2026-04-19  
**Error:** `AttributeError: module 'flet' has no attribute 'FilePickerResultEvent'`  
**File:** `src/app/main.py` line 99  
**Status:** ✅ FIXED

**Solution:**
- Removed type hint: `e: ft.FilePickerResultEvent`
- Changed to untyped parameter: `def on_file_selected(e):`
- Flet doesn't expose this type in its public API

---

### Failure #4: Asyncio.Sleep Coroutine Not Awaited
**Date:** 2026-04-19  
**Error:** `RuntimeWarning: coroutine 'sleep' was never awaited`  
**File:** `src/app/main.py` line 88  
**Status:** ✅ FIXED

**Solution:**
- Removed line: `asyncio.sleep(0.5)`
- FilePicker overlay doesn't need async sleep
- Replaced with synchronous page update

---

## 🛡️ Error Handling Features

### 1. Application-Level Exception Handler
**Location:** `app.py`

```python
def main_wrapper(page):
    """Wrapper around main to catch and log all exceptions."""
    try:
        return main(page)
    except Exception as e:
        logger.error(f"CRITICAL: Uncaught exception in main: {e}")
        logger.error(traceback.format_exc())
        raise
```

**Features:**
- Catches all uncaught exceptions
- Logs full stack trace
- Attempts to show error on UI
- Re-raises for proper crash handling

### 2. Pipeline Controller Error Logging
**Location:** `src/app/controllers.py`

```python
async def run_pipeline(...):
    try:
        # Pipeline execution
    except Exception as ex:
        logger.error(f"Pipeline execution failed: {ex}")
        logger.error(traceback.format_exc())
        log_callback(f"[ERROR] {str(ex)}", "ERROR")
```

**Features:**
- Logs to file and console
- Shows error in UI terminal
- Continues without crashing app
- Preserves UI responsiveness

### 3. File Operation Error Handling
**Location:** `core/render.py` and `core/transcription.py`

**Before:**
```python
subprocess.run(extract_cmd, ..., check=True)
```

**After:**
```python
try:
    result = subprocess.run(extract_cmd, ..., stderr=subprocess.PIPE, text=True, check=True)
except FileNotFoundError:
    logger.error("FFmpeg not found in PATH")
    raise
except subprocess.CalledProcessError as e:
    logger.error(f"FFmpeg failed: {e.stderr}")
    raise
```

**Features:**
- Captures stderr from FFmpeg
- Logs specific error messages
- Checks for missing files before execution
- Creates output directories automatically

---

## 📊 How to Check Logs

### During Runtime
1. Check `logs/session_log.txt` for all activity
2. Check `logs/error_log.txt` for errors only
3. Watch console output for immediate errors

### After Crash
1. Open `logs/error_log.txt` first (errors only)
2. If empty, check `logs/session_log.txt` (all logs)
3. Look for `[ERROR]` or `CRITICAL` markers
4. Check for stack traces (show last error first)

### Search for Specific Errors
```bash
# Find all errors in session log
Get-Content logs/session_log.txt | Select-String "ERROR|CRITICAL"

# Find errors only
Get-Content logs/error_log.txt

# Follow log file in real-time
Get-Content -Path logs/session_log.txt -Tail 10 -Wait
```

---

## 🚀 Testing Failure Detection

### Test 1: FFmpeg Missing
**Setup:** Rename FFmpeg executable  
**Expected:** Error logged to `logs/error_log.txt`  
**Result:** Will show "FFmpeg not found in PATH"

### Test 2: Invalid VOD Path
**Setup:** Enter non-existent file path  
**Expected:** Error logged and shown in UI  
**Result:** "Invalid file path. Please paste a valid MP4/MKV path."

### Test 3: Transcription Failure
**Setup:** Provide corrupted audio file  
**Expected:** Error logged with Whisper error details  
**Result:** Will show transcription error message

### Test 4: GPU Out of Memory
**Setup:** Process very large video  
**Expected:** CUDA OOM error logged  
**Result:** Will show memory error and fall back to CPU

---

## 📝 Log Entry Format

All logs follow this format:
```
TIMESTAMP - LOGGER_NAME - LOG_LEVEL - MESSAGE
2026-04-19 10:48:46,395 - src.app.main - INFO - KREATOR KLIP - Application Started
```

**Log Levels:**
- `DEBUG` - Detailed debugging information
- `INFO` - General informational messages
- `WARNING` - Warning messages (potential issues)
- `ERROR` - Error messages (things went wrong)
- `CRITICAL` - Critical errors (app may crash)

---

## ✅ Current Logging Coverage

### Application Startup
- ✅ Application initialization logged
- ✅ Flet framework initialization logged
- ✅ Configuration loading logged
- ✅ Uncaught exceptions logged

### Pipeline Execution
- ✅ Pipeline start/stop logged
- ✅ Scanner stage logged
- ✅ Validator stage logged
- ✅ Cutter stage logged
- ✅ Finisher stage logged
- ✅ Render progress logged
- ✅ FFmpeg commands logged
- ✅ Errors and exceptions logged

### Hardware Detection
- ✅ GPU detection logged
- ✅ CPU core count logged
- ✅ VRAM detection logged
- ✅ Hardware profile tier logged

### File Operations
- ✅ File existence checks logged
- ✅ Directory creation logged
- ✅ File access errors logged
- ✅ FFmpeg stderr captured

### Audio Processing
- ✅ Audio extraction logged
- ✅ Spike detection logged
- ✅ Transcription attempts logged
- ✅ Model loading failures logged

---

## 🔧 How to Add More Logging

### In Any Python Module
```python
import logging
logger = logging.getLogger(__name__)

# Log messages
logger.info("This is an info message")
logger.warning("This is a warning")
logger.error("This is an error")
logger.critical("This is a critical error")
logger.debug("This is debug info")

# Log with traceback
try:
    risky_operation()
except Exception as e:
    logger.error(f"Operation failed: {e}")
    logger.error(traceback.format_exc())
```

### Best Practices
1. Always include context (what, why, where)
2. Use appropriate log level
3. Include variable values for debugging
4. Log both errors and successes
5. Use traceback for exceptions

---

## 📞 Troubleshooting Guide

| Symptom | Solution | Check Log |
|---------|----------|-----------|
| App crashes silently | Check error_log.txt | error_log.txt |
| Pipeline fails | Check session_log.txt for [ERROR] | session_log.txt |
| No output files | Check file creation logs | session_log.txt + "Finisher" |
| FFmpeg errors | Check FFmpeg stderr in logs | error_log.txt |
| Memory issues | Check VRAM logs | session_log.txt + "VRAM" |
| Transcription fails | Check Whisper model logs | error_log.txt |

---

## 📌 Important Locations

- **Logging Config:** [src/app/main.py](src/app/main.py#L11-L40)
- **Error Handler:** [app.py](app.py#L10-L23)
- **Pipeline Logging:** [src/app/controllers.py](src/app/controllers.py#L84-L133)
- **FFmpeg Errors:** [core/render.py](core/render.py#L337-L358)

---

## ✨ Summary

The KreatorKlip application now has:
- ✅ Comprehensive multi-level logging
- ✅ Error capture at all levels
- ✅ Stack traces for debugging
- ✅ FFmpeg error details
- ✅ Application crash protection
- ✅ User-friendly error messages
- ✅ Persistent failure logs

**All future failures will be captured and logged automatically!**

---

Generated: 2026-04-19
