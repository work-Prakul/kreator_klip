from faster_whisper import WhisperModel
import ffmpeg
import os
import torch
import gc

def format_time_ass(seconds: float) -> str:
    """Converts seconds to HH:MM:SS.CC ASS format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centisecs = int((seconds - int(seconds)) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"

def run_finisher(clip_path: str, final_path: str, ui_callback):
    """
    Stage 4: The Stylist.
    Transcription with Whisper Large-V3 and burned-in styled subtitles.
    """
    ui_callback("Finisher: Generating high-fidelity captions (Large-V3)...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"
    
    # 1. Model Interference
    # Check VRAM - RTX 3060 has 12GB, Large-V3 needs ~5-6GB depending on settings
    ui_callback("Finisher: Loading model into VRAM...")
    model = WhisperModel("large-v3", device=device, compute_type=compute_type)
    segments, _ = model.transcribe(clip_path, word_timestamps=True)
    
    # 2. .ASS Subtitle Formatting
    ass_path = clip_path.replace(".mp4", ".ass").replace("raw_", "style_")
    
    # Style: Yellow, Bold, Black Outline
    # PrimaryColour: &H0000FFFF (Yellow)
    # OutlineColour: &H00000000 (Black)
    # Bold: -1 (Yes)
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,85,&H0000FFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,0,2,10,10,250,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    
    ui_callback("Finisher: Formatting word-level timestamps...")
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header)
        for seg in segments:
            for word in seg.words:
                s_t = format_time_ass(word.start)
                e_t = format_time_ass(word.end)
                f.write(f"Dialogue: 0,{s_t},{e_t},Default,,0,0,0,,{word.word.strip()}\n")
                
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    gc.collect()
    
    # 3. Burn Subtitles
    ui_callback("Finisher: Burning subtitles into video stream...")
    
    # Escape path for FFmpeg filter
    safe_ass_path = ass_path.replace('\\', '/').replace(':', '\\:')
    
    try:
        stream = ffmpeg.input(clip_path)
        video = stream.video.filter('ass', safe_ass_path)
        audio = stream.audio
        
        # Hardware Encoding Fallback
        vcodec = 'h264_nvenc' if device == "cuda" else 'libx264'
        options = {'preset': 'p4', 'tune': 'hq'} if device == "cuda" else {'preset': 'fast'}
        
        out = ffmpeg.output(video, audio, final_path, vcodec=vcodec, **options)
        out = out.overwrite_output()
        out.run(quiet=True, capture_stdout=True, capture_stderr=True)
    except ffmpeg.Error as e:
        ui_callback(f"Finisher [ERROR] Burn-in Failed: {e.stderr.decode() if e.stderr else str(e)}")
        # CPU Fallback
        out = ffmpeg.output(video, audio, final_path, vcodec='libx264', preset='fast')
        out = out.overwrite_output()
        out.run(quiet=True)
        
    # Cleanup temp files
    if os.path.exists(ass_path): os.remove(ass_path)
    if os.path.exists(clip_path): os.remove(clip_path)
    
    ui_callback(f"Finisher: EXPORTED -> {os.path.basename(final_path)}")
    return final_path
