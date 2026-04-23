import json
import os

with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

# Part 1
config["whisper_language"] = "hi"
config["whisper_multilingual"] = True

# Part 4
config["enable_subtitles"] = False

# Part 2: Add keywords
config["game_profiles"]["valorant"]["keywords"] = ["अरे", "भाई", "क्या", "मार दिया", "बच गया", "एस", "क्लच", "हेडशॉट", "निकाल", "भाग", "आ गया", "कमाल", "ace", "clutch", "headshot", "nice", "wow"]
config["game_profiles"]["cs2"]["keywords"] = ["भाई", "मार दिया", "बम", "प्लांट", "डिफ्यूज", "हेडशॉट", "निकाल", "क्लच", "बच गया", "कमाल", "headshot", "planted", "clutch", "no way"]
config["game_profiles"]["delta_force"]["keywords"] = ["मार दिया", "भाई", "आ गया", "निकाल", "हेडशॉट", "ऑब्जेक्टिव", "क्लच", "बच गया", "kill", "headshot", "objective"]

# Part 5: Add vision killfeed settings
config["vision"]["enable_killfeed_ocr"] = True
config["vision"]["player_handles"] = ["wildflame", "wildflame75"]
config["vision"]["spectator_strings"] = ["spectating", "observer"]

# Part 6: Vision motion threshold
config["vision"]["motion_threshold"] = 0.12
config["vision"]["motion_threshold_note"] = "Increase if menus/lobbies appear in output. Decrease if valid kill clips are being dropped."

with open("config.json", "w", encoding="utf-8") as f:
    json.dump(config, f, indent=2, ensure_ascii=False)
