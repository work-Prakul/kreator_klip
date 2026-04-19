"""
KREATOR KLIP - High-Fidelity Renderer
Direct subprocess-based FFmpeg with hardware acceleration and progress tracking.
Optimized for RTX 3060 (12GB) with CUDA hardware acceleration.
"""
import os
import logging
import subprocess
import re
import threading
import time
from typing import Callable, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RenderProgress:
    """Progress tracking for a single render operation."""
    clip_id: int
    percentage: float
    current_time: Optional[str] = None
    total_duration: Optional[float] = None
    status: str = "IDLE"  # IDLE | PROCESSING | COMPLETED | FAILED


class ProgressParser:
    """
    Thread-safe parser for FFmpeg stderr output to extract real-time progress.
    """
    
    def __init__(self):
        self._lock = threading.Lock()
        self._current_progress: float = 0.0
        self._current_time: Optional[str] = None
        self._total_duration: Optional[float] = None
        
    def parse_line(self, line: str) -> Optional[RenderProgress]:
        """
        Parse FFmpeg stderr line for progress information.
        
        FFmpeg outputs progress like:
        frame=  123 fps= 30 q=28.0 size=   56789kB time=00:00:05.12 bitrate=1234.5kbits/s speed= 2.0x
        
        Returns:
            RenderProgress object or None if no progress found
        """
        if not line:
            return None
        
        # Pattern: time=HH:MM:SS.mmm
        time_match = re.search(r'time=(\d{2}):(\d{2}):(\d{2})\.(\d+)', line)
        
        if time_match:
            hours = int(time_match.group(1))
            minutes = int(time_match.group(2))
            seconds = int(time_match.group(3))
            millis = int(time_match.group(4))
            
            total_seconds = hours * 3600 + minutes * 60 + seconds + millis / 1000.0
            
            # Try to find total duration from stream info
            duration_match = re.search(r'duration=(\d{2}):(\d{2}):(\d{2})\.(\d+)', line)
            if duration_match:
                dh = int(duration_match.group(1))
                dm = int(duration_match.group(2))
                ds = int(duration_match.group(3))
                dms = int(duration_match.group(4))
                total_seconds = dh * 3600 + dm * 60 + ds + dms / 1000.0
                self._total_duration = total_seconds
            
            # Calculate percentage
            if self._total_duration and total_seconds > 0:
                percentage = (total_seconds / self._total_duration) * 100
            else:
                percentage = min(percentage, 100.0) if self._total_duration else 50.0
            
            with self._lock:
                self._current_progress = percentage
                self._current_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"
            
            return RenderProgress(
                clip_id=0,  # Will be set by caller
                percentage=percentage,
                current_time=self._current_time,
                total_duration=self._total_duration
            )
        
        return None
    
    def get_progress(self, clip_id: int) -> RenderProgress:
        """Get current progress for a clip."""
        with self._lock:
            return RenderProgress(
                clip_id=clip_id,
                percentage=self._current_progress,
                current_time=self._current_time,
                total_duration=self._total_duration
            )


class HardwareAcceleratedRenderer:
    """
    FFmpeg wrapper with direct subprocess calls for maximum control.
    Forces CUDA hardware acceleration with NVENC.
    """
    
    def __init__(self, progress_callback: Optional[Callable[[int, float], None]] = None):
        """
        Initialize renderer.
        
        Args:
            progress_callback: Function(clip_id, percentage) -> None called every 500ms
        """
        self.progress_callback = progress_callback
        self.parser = ProgressParser()
        self._progress_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
    def _ffmpeg_cmd(self, input_path: str, output_path: str, 
                    start_time: float = 0, duration: float = 30.0,
                    crop_916: bool = True, facecam: Optional[dict] = None,
                    force_cpu: bool = False) -> Tuple[bool, str]:
        """
        Build and execute FFmpeg command with hardware acceleration.
        
        Returns:
            Tuple (success, error_message)
        """
        # FFmpeg command with CUDA hardware acceleration
        cmd = [
            "ffmpeg",
            "-hwaccel", "cuda",  # Force CUDA hardware acceleration
            "-i", input_path,
            "-ss", str(start_time),
            "-t", str(duration),
            "-c:v", "h264_nvenc" if not force_cpu else "libx264",
            "-preset", "p4",  # Performance preset 4 (balanced)
            "-c:a", "copy",
            "-y",  # Overwrite output
            output_path
        ]
        
        # Add facecam overlay if specified
        if facecam and facecam.get("x", 0) > 0:
            x = facecam["x"]
            y = facecam["y"]
            w = facecam["w"]
            h = facecam["h"]
            
            # Extract and overlay facecam
            cmd.extend([
                "-filter_complex",
                f"[0:v][1:v]crop=w={w}:h={h}:x={x}:y={y}[face];"
                f"[0:v]crop=iw*9/16:ih[main];[main]scale=1080:1920[crop];"
                f"[crop][face]overlay=0:0[out]",
                "-map", "[out]",
                "-i", f"{facecam.get('source', '')}",
                "-map", "0:v:1"
            ])
        
        # Add crop filter if needed
        if crop_916:
            cmd.extend([
                "-filter_complex",
                "[0:v]crop=iw*9/16:ih[main];[main]scale=1080:1920[out]"
            ])
            cmd.extend(["-map", "[out]"])
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                text=True,
                bufsize=1
            )
            
            # Read stderr in background thread for progress
            def read_stderr():
                try:
                    for line in process.stderr:
                        if self._stop_event.is_set():
                            break
                        progress = self.parser.parse_line(line)
                        if progress:
                            progress.clip_id = 0  # Will be updated by caller
                            if self.progress_callback:
                                self.progress_callback(0, progress.percentage)
                except Exception as e:
                    logger.error(f"Progress parsing error: {e}")
            
            self._stop_event.clear()
            self._progress_thread = threading.Thread(target=read_stderr, daemon=True)
            self._progress_thread.start()
            
            # Wait for completion
            return_code = process.wait(timeout=3600)  # 1 hour timeout
            
            if self._progress_thread:
                self._stop_event.set()
                self._progress_thread.join(timeout=1)
            
            success = return_code == 0
            error_msg = process.stderr.read() if not success else ""
            
            return success, error_msg
            
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg timeout")
            return False, "Timeout"
        except Exception as e:
            logger.error(f"FFmpeg error: {e}")
            return False, str(e)
    
    def render_clip(self, clip_id: int, input_path: str, output_path: str,
                   start_time: float, duration: float, config: dict) -> RenderProgress:
        """
        Render a single clip with progress tracking.
        
        Args:
            clip_id: Unique identifier for this clip
            input_path: Source video path
            output_path: Output video path
            start_time: Start timestamp for extraction
            duration: Duration to extract
            config: Configuration dict with facecam coords
            
        Returns:
            RenderProgress object
        """
        progress = RenderProgress(
            clip_id=clip_id,
            percentage=0.0,
            status="PROCESSING"
        )
        
        try:
            # Update progress to 10%
            if self.progress_callback:
                self.progress_callback(clip_id, 10.0)
            
            # Execute render
            success, error = self._ffmpeg_cmd(
                input_path=input_path,
                output_path=output_path,
                start_time=start_time,
                duration=duration,
                crop_916=True,
                facecam=config.get("facecam_coords"),
                force_cpu=config.get("hardware_overrides", {}).get("force_cpu", False)
            )
            
            if success:
                progress.status = "COMPLETED"
                progress.percentage = 100.0
                logger.info(f"Clip {clip_id}: Rendered successfully!")
            else:
                progress.status = "FAILED"
                progress.percentage = 0.0
                logger.error(f"Clip {clip_id}: Render failed - {error}")
            
            return progress
            
        except Exception as e:
            progress.status = "FAILED"
            progress.percentage = 0.0
            logger.error(f"Clip {clip_id}: Exception - {e}")
            return progress


def detect_silence(input_path: str, duration: float = 1.5, noise_db: str = "-30dB") -> list:
    """
    Runs FFmpeg silencedetect to find silent portions.
    Returns a list of (start, end) silent windows.
    """
    logger.info("Cutter: Running silence detection...")
    try:
        # Run ffmpeg with silencedetect
        cmd = [
            "ffmpeg", "-i", input_path, 
            "-af", f"silencedetect=noise={noise_db}:d={duration}", 
            "-f", "null", "-"
        ]
        result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True, timeout=60)
        
        silences = []
        lines = result.stderr.split('\n')
        
        silence_start = None
        for line in lines:
            if "silence_start" in line:
                parts = line.split("silence_start: ")
                if len(parts) > 1:
                    silence_start = float(parts[-1].split()[0])
            elif "silence_end" in line:
                parts = line.split("silence_end: ")
                if len(parts) > 1 and silence_start is not None:
                    silence_end = float(parts[-1].split()[0])
                    silences.append((silence_start, silence_end))
                    silence_start = None
                    
        return silences
    except Exception as e:
        logger.error(f"Cutter: Silence detection failed: {e}")
        return []


def run_cutter_stage(input_video: str, locked_event_t: float, output_path: str, 
                    config: dict, progress_callback: Optional[Callable[[int, float], None]] = None) -> Optional[str]:
    """
    Stage 3: Extract 30s window, truncate silence, crop 9:16, overlay facecam.
    Returns the path to the cut clip, or None if failed.
    
    Hardware Acceleration:
    - hwaccel cuda
    - c:v h264_nvenc with -preset p4
    - Progress parsing from stderr
    """
    logger.info(f"=== STAGE 3: THE CUTTER (Event @ {locked_event_t:.2f}s) ===")
    
    try:
        # Verify input file exists
        if not os.path.exists(input_video):
            logger.error(f"Cutter: Input video file not found: {input_video}")
            return None
        
        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        start_t = max(0, locked_event_t - 10.0)
        end_t = locked_event_t + 20.0
        duration = end_t - start_t
        
        # Temp intermediate 30s clip
        temp_30s = output_path.replace(".mp4", "_30s.mp4")
        
        # 1. Extract the raw 30s window quickly (no processing yet)
        logger.info("Cutter: Extracting 30s window...")
        
        # Direct subprocess for extraction
        extract_cmd = [
            "ffmpeg", "-i", input_video,
            "-ss", str(start_t),
            "-t", str(duration),
            "-c:v", "copy",
            "-c:a", "copy",
            "-y",
            temp_30s
        ]
        
        try:
            result = subprocess.run(extract_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, check=True, timeout=300)
        except FileNotFoundError:
            logger.error("Cutter: FFmpeg not found in PATH. Please install FFmpeg.")
            raise
        except subprocess.CalledProcessError as e:
            logger.error(f"Cutter: FFmpeg extraction failed: {e.stderr}")
            raise
        except subprocess.TimeoutExpired:
            logger.error(f"Cutter: FFmpeg extraction timed out")
            raise
        logger.info("Cutter: 30s window extracted.")
        
        # 2. Silence Truncation
        silences = detect_silence(temp_30s)
        working_input = temp_30s
        temp_truncated = output_path.replace(".mp4", "_trunc.mp4")
        
        if silences:
            logger.info(f"Cutter: Splicing out {len(silences)} sections of dead air...")
            
            # Build concat file
            concat_path = output_path.replace(".mp4", "_concat.txt")
            with open(concat_path, "w") as f:
                current_time = 0.0
                for (s_start, s_end) in silences:
                    if s_start > current_time:
                        f.write(f"file '{os.path.basename(temp_30s)}'\n")
                        f.write(f"inpoint_b {current_time}\n")
                        f.write(f"outpoint_b {s_start}\n")
                    current_time = s_end
                
                # Add final chunk
                if current_time < duration:
                    f.write(f"file '{os.path.basename(temp_30s)}'\n")
                    f.write(f"inpoint_b {current_time}\n")
                    f.write(f"outpoint_b {duration + 1.0}\n")
            
            # Run concat
            try:
                subprocess.run([
                    "ffmpeg", "-f", "concat", "-safe", "0",
                    "-i", concat_path, "-c", "copy", "-y", temp_truncated
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=300)
                working_input = temp_truncated
                logger.info("Cutter: Silence truncation complete.")
            except subprocess.CalledProcessError:
                logger.warning("Cutter: Safe concat failed. Using full clip.")
                os.remove(concat_path)
                working_input = temp_30s
        else:
            working_input = temp_30s
        
        # 3. Framing & Face-cam with Hardware Acceleration
        logger.info("Cutter: Applying 9:16 Crop and Face-cam Overlay (CUDA NVENC)...")
        
        # Use the hardware accelerated renderer
        renderer = HardwareAcceleratedRenderer(progress_callback)
        
        progress = renderer.render_clip(
            clip_id=1,  # Will be updated by caller
            input_path=working_input,
            output_path=output_path,
            start_time=0,  # Already extracted
            duration=duration,
            config=config
        )
        
        # Cleanup temp files
        for path in [temp_30s, temp_truncated, output_path.replace(".mp4", "_concat.txt")]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass
        
        if progress.status == "COMPLETED":
            logger.info(f"Cutter: Hardware encoding (NVENC) successful.")
            return output_path
        else:
            logger.error(f"Cutter: Failed on timestamp {locked_event_t}")
            return None
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Cutter: FFmpeg called process error at {locked_event_t}: {e}")
        return None
    except subprocess.TimeoutExpired:
        logger.error(f"Cutter: Timeout at {locked_event_t}")
        return None
    except Exception as e:
        logger.error(f"Cutter: Failed strictly on timestamp {locked_event_t}: {e}")
        return None
