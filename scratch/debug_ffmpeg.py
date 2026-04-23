import ffmpeg
import os

trimmed_clip_path = r"temp\raw_event_1.mp4"
ass_path = r"temp\raw_event_1.ass"
final_output_path = r"output\test_debug.mp4"

# Mocking the generation of .ass if it doesn't exist for test
if not os.path.exists(ass_path):
    with open(ass_path, "w") as f:
        f.write("[Script Info]\nTitle: Test\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\nDialogue: 0,0:00:00.00,0:00:05.00,Default,,0,0,0,,Test Subtitle")

safe_ass_path = ass_path.replace("\\", "/").replace(":", "\\:")
print(f"Safe ASS path: {safe_ass_path}")

stream = ffmpeg.input(trimmed_clip_path)
video = stream.video.filter("ass", safe_ass_path)
audio = stream.audio

try:
    print("Running ffmpeg...")
    ffmpeg.output(video, audio, final_output_path, vcodec="h264_nvenc").overwrite_output().run(capture_stdout=True, capture_stderr=True)
    print("Success!")
except ffmpeg.Error as e:
    print("FFmpeg Error!")
    print(e.stderr.decode())
