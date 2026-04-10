import ffmpeg
import torch
import os

def run_cutter(video_path: str, event: float, output_path: str, facecam: dict, ui_callback):
    """
    Stage 3: The Knife.
    Crops 16:9 to 9:16 and overlays face-cam using NVENC hardware acceleration.
    """
    ui_callback(f"Cutter: Processing 30s highlight window at {event:.2f}s...")
    
    # 10s before, 20s total window (per blueprint context usually 30s)
    # The requirement didn't specify duration, but 30s is standard for highlights.
    start_time = max(0, event - 10.0)
    duration = 30.0
    
    # Base Stream Selection
    stream = ffmpeg.input(video_path, ss=start_time, t=duration)
    
    # 9:16 Main Crop Filter (assuming original is 1920x1080)
    # Target 1080x1920
    # Crop center 16:9 (1080x1920) is usually just 'ih*9/16':'ih' then scale to 1080x1920
    main_vid = stream.video.filter('crop', 'ih*9/16', 'ih').filter('scale', 1080, 1920)
    
    # Face-cam logic
    if facecam and facecam.get("w", 0) > 0:
        fx, fy, fw, fh = facecam.get("x", 0), facecam.get("y", 0), facecam.get("w", 400), facecam.get("h", 225)
        face_vid = stream.video.filter('crop', fw, fh, fx, fy)
        # Scale face-cam to wide (full width of canvas)
        face_scaled = face_vid.filter('scale', 1080, -1)
        # Overlay at top (y=0)
        final_video = ffmpeg.overlay(main_vid, face_scaled, x=0, y=0)
    else:
        final_video = main_vid
        
    audio = stream.audio
    
    # RTX 3060 Encoding Parameters
    is_cuda = torch.cuda.is_available()
    vcodec = 'h264_nvenc' if is_cuda else 'libx264'
    options = {
        'preset': 'p4',
        'tune': 'hq',
        'video_track_timescale': 60000 # Performance tip
    } if is_cuda else {'preset': 'fast'}
    
    ui_callback(f"Cutter: Executing NVENC Hardware Encode (Preset: {options.get('preset')})...")
    
    try:
        out = ffmpeg.output(final_video, audio, output_path, vcodec=vcodec, **options)
        out = out.overwrite_output()
        out.run(quiet=True, capture_stdout=True, capture_stderr=True)
    except ffmpeg.Error as e:
        ui_callback(f"Cutter [ERROR] Primary encode failed, falling back to CPU: {e.stderr.decode() if e.stderr else str(e)}")
        out = ffmpeg.output(final_video, audio, output_path, vcodec='libx264', preset='fast')
        out = out.overwrite_output()
        out.run(quiet=True)
        
    return output_path
