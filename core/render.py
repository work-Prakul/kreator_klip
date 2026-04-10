import ffmpeg
import os
import logging
import subprocess

def detect_silence(input_path: str, duration: float = 1.5, noise_db: str = "-30dB"):
    """
    Runs FFmpeg silencedetect to find silent portions.
    Returns a list of (start, end) silent windows.
    """
    logging.info("Cutter: Running silence detection...")
    try:
        # Run ffmpeg with silencedetect
        cmd = [
            "ffmpeg", "-i", input_path, 
            "-af", f"silencedetect=noise={noise_db}:d={duration}", 
            "-f", "null", "-"
        ]
        result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
        
        silences = []
        lines = result.stderr.split('\n')
        
        silence_start = None
        for line in lines:
            if "silence_start" in line:
                # e.g.: [silencedetect @ 00xyz] silence_start: 3.5
                parts = line.split("silence_start: ")
                if len(parts) > 1:
                    silence_start = float(parts[-1].split()[0])
            elif "silence_end" in line:
                # e.g.: [silencedetect @ 00xyz] silence_end: 5.5 | silence_duration: 2.0
                parts = line.split("silence_end: ")
                if len(parts) > 1 and silence_start is not None:
                    silence_end = float(parts[-1].split()[0])
                    silences.append((silence_start, silence_end))
                    silence_start = None
                    
        return silences
    except Exception as e:
        logging.error(f"Cutter: Silence detection failed: {e}")
        return []

def run_cutter_stage(input_video: str, locked_event_t: float, output_path: str, config: dict):
    """
    Stage 3: Extract 30s window, truncate silence, crop 9:16, overlay facecam.
    Returns the path to the cut clip, or None if failed.
    """
    logging.info(f"--- STAGE 3: THE CUTTER (Event @ {locked_event_t:.2f}s) ---")
    try:
        start_t = max(0, locked_event_t - 10.0)
        end_t = locked_event_t + 20.0
        duration = end_t - start_t
        
        # Temp intermediate 30s clip
        temp_30s = output_path.replace(".mp4", "_30s.mp4")
        
        # 1. Extract the raw 30s window quickly (no processing yet)
        logging.info("Cutter: Extracting 30s window...")
        (
            ffmpeg
            .input(input_video, ss=start_t, t=duration)
            .output(temp_30s, vcodec="copy", acodec="copy")
            .overwrite_output()
            .run(quiet=True)
        )
        
        # 2. Silence Truncation
        silences = detect_silence(temp_30s)
        working_input = temp_30s
        temp_truncated = output_path.replace(".mp4", "_trunc.mp4")
        
        if silences:
            logging.info(f"Cutter: Splicing out {len(silences)} sections of dead air...")
            # Rather than complex concat strings, we'll build a fast FFmpeg concat file
            concat_path = output_path.replace(".mp4", "_concat.txt")
            with open(concat_path, "w") as f:
                # invert silences to get "keep" chunks
                current_time = 0.0
                for (s_start, s_end) in silences:
                    if s_start > current_time:
                        f.write(f"file '{os.path.basename(temp_30s)}'\n")
                        f.write(f"inpoint_b {current_time}\n")
                        f.write(f"outpoint_b {s_start}\n")
                    current_time = s_end
                
                # add the final chunk
                if current_time < duration:
                    f.write(f"file '{os.path.basename(temp_30s)}'\n")
                    f.write(f"inpoint_b {current_time}\n")
                    f.write(f"outpoint_b {duration + 1.0}\n")  # safe overshoot
            
            # Run concat command
            try:
                # To prevent concat issues, we recode briefly or use safe concat
                subprocess.run([
                    "ffmpeg", "-f", "concat", "-safe", "0", 
                    "-i", concat_path, "-c", "copy", "-y", temp_truncated
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                working_input = temp_truncated
            except subprocess.CalledProcessError:
                logging.warning("Cutter: Safe concat failed. Falling back to non-truncated.")
                working_input = temp_30s
        
        # 3. Framing & Face-cam complex filter graph
        logging.info("Cutter: Applying 9:16 Crop and Face-cam Overlay (Hardware Accelerated)...")
        face_rect = config.get("face_cam_rect")
        
        stream = ffmpeg.input(working_input)
        
        # Main center crop
        main_vid = stream.video.filter('crop', 'ih*9/16', 'ih').filter('scale', 1080, 1920)
        
        if face_rect:
            x, y, w, h = face_rect["x"], face_rect["y"], face_rect["w"], face_rect["h"]
            # Extract face-cam
            face_vid = stream.video.filter('crop', w, h, x, y)
            # Scale face-cam to fit width of 1080 (vertical mode width)
            face_scaled = face_vid.filter('scale', 1080, -1)
            # Overlay at top (y=0)
            final_video = ffmpeg.overlay(main_vid, face_scaled, x=0, y=0)
        else:
            final_video = main_vid
            
        audio = stream.audio
        
        # Encoding priority: NVENC -> CPU
        hardware_overrides = config.get("hardware_overrides", {})
        force_cpu = hardware_overrides.get("force_cpu", False)
        
        enc_success = False
        if not force_cpu:
            try:
                out = ffmpeg.output(final_video, audio, output_path, vcodec='h264_nvenc', preset='fast')
                out = out.overwrite_output()
                ffmpeg.run(out, quiet=True)
                enc_success = True
                logging.info("Cutter: Hardware encoding (NVENC) successful.")
            except ffmpeg.Error as e:
                logging.warning(f"Cutter: NVENC failed, falling back to libx264. {e.stderr.decode() if e.stderr else e}")
                
        if not enc_success:
            out = ffmpeg.output(final_video, audio, output_path, vcodec='libx264', preset='fast')
            out = out.overwrite_output()
            ffmpeg.run(out, quiet=True)
            logging.info("Cutter: CPU encoding successful.")
            
        # Cleanup
        for path in [temp_30s, temp_truncated, output_path.replace(".mp4", "_concat.txt")]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass
                    
        return output_path
        
    except Exception as e:
        logging.error(f"Cutter: Failed strictly on timestamp {locked_event_t}: {e}")
        return None
