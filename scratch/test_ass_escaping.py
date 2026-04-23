import os
import logging
import ffmpeg

def format_time_ass(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centisecs = int((seconds - int(seconds)) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"

def generate_ass(segment_data, output_ass_path: str):
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,90,&H0000FFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,2,10,10,250,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    with open(output_ass_path, "w", encoding="utf-8") as f:
        f.write(header)
        for seg in segment_data:
            start_time = format_time_ass(seg["start"])
            end_time = format_time_ass(seg["end"])
            text = seg["text"].strip()
            f.write(f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text}\n")

# Test with real logic
trimmed_clip_path = r"temp\raw_event_1.mp4"
ass_path = r"temp\test_real.ass"
final_output_path = r"output\test_real.mp4"

segment_data = [{"start": 0.0, "end": 5.0, "text": "Hello world"}]
generate_ass(segment_data, ass_path)

# Option 1: Current escaping
safe_ass_path = ass_path.replace("\\", "/").replace(":", "\\:")
print(f"Option 1 path: {safe_ass_path}")

try:
    stream = ffmpeg.input(trimmed_clip_path)
    video = stream.video.filter("ass", safe_ass_path)
    audio = stream.audio
    ffmpeg.output(video, audio, final_output_path, vcodec="h264_nvenc").overwrite_output().run(capture_stdout=True, capture_stderr=True)
    print("Option 1 Success!")
except ffmpeg.Error as e:
    print("Option 1 Failed!")
    # print(e.stderr.decode())

# Option 2: Absolute path escaping
abs_ass_path = os.path.abspath(ass_path)
safe_ass_path_2 = abs_ass_path.replace("\\", "/").replace(":", "\\:")
print(f"Option 2 path: {safe_ass_path_2}")

try:
    stream = ffmpeg.input(trimmed_clip_path)
    video = stream.video.filter("ass", safe_ass_path_2)
    audio = stream.audio
    ffmpeg.output(video, audio, final_output_path, vcodec="h264_nvenc").overwrite_output().run(capture_stdout=True, capture_stderr=True)
    print("Option 2 Success!")
except ffmpeg.Error as e:
    print("Option 2 Failed!")
    # print(e.stderr.decode())

# Option 3: Relative path with ./
safe_ass_path_3 = "./" + ass_path.replace("\\", "/")
print(f"Option 3 path: {safe_ass_path_3}")

try:
    stream = ffmpeg.input(trimmed_clip_path)
    video = stream.video.filter("ass", safe_ass_path_3)
    audio = stream.audio
    ffmpeg.output(video, audio, final_output_path, vcodec="h264_nvenc").overwrite_output().run(capture_stdout=True, capture_stderr=True)
    print("Option 3 Success!")
except ffmpeg.Error as e:
    print("Option 3 Failed!")
