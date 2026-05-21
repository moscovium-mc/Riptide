"""Application constants, settings persistence, and FFmpeg detection."""

import json
import os
import shutil
import subprocess
from pathlib import Path

APP_NAME = "yt-dlp GUI"
APP_VERSION = "2026.05.20"
CONFIG_DIR = Path.home() / ".config" / "yt-dlp-gui"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_DOWNLOAD_DIR = str(Path.home() / "Downloads")

VIDEO_FORMATS = {
    "Best": "bv*+ba/b",
    "Best Video": "bv*",
    "1080p": "bv*[height<=1080]+ba/b[height<=1080]",
    "720p": "bv*[height<=720]+ba/b[height<=720]",
    "480p": "bv*[height<=480]+ba/b[height<=480]",
    "360p": "bv*[height<=360]+ba/b[height<=360]",
    "Worst": "w",
}

AUDIO_FORMATS = {
    "MP3": ("mp3", "192"),
    "AAC": ("aac", "192"),
    "FLAC": ("flac", "0"),
    "Opus": ("opus", "192"),
    "WAV": ("wav", "0"),
    "M4A": ("m4a", "192"),
}

DEFAULT_SETTINGS = {
    "mode": "video",
    "format": "Best",
    "audio_format": "MP3",
    "audio_quality": 192,
    "output_dir": DEFAULT_DOWNLOAD_DIR,
    "naming_template": "Default",
    "custom_template": "",
    "embed_metadata": True,
    "ffmpeg_path": "",
    "last_urls": [],
}


def load_settings():
    """Load settings from config.json, merging with defaults."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    settings = DEFAULT_SETTINGS.copy()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            settings.update(saved)
        except (json.JSONDecodeError, OSError):
            pass
    return settings


def save_settings(settings):
    """Persist settings to config.json."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except OSError:
        pass


def find_ffmpeg(custom_path=""):
    """Locate ffmpeg binary. Returns path or None."""
    candidates = []
    if custom_path and os.path.isfile(custom_path):
        candidates.append(custom_path)
    candidates.extend([
        "ffmpeg",
        str(Path.home() / "Desktop" / "FFmpeg" / "ffmpeg.exe"),
        str(Path.home() / "Desktop" / "FFmpeg" / "bin" / "ffmpeg.exe"),
        str(Path.home() / "Desktop" / "FFmpeg" / "ffmpeg"),
        str(Path.home() / "Desktop" / "FFmpeg" / "bin" / "ffmpeg"),
    ])
    for path in candidates:
        if shutil.which(path) or os.path.isfile(path):
            return path if os.path.isfile(path) else shutil.which(path)
    return None


def get_ffmpeg_version(ffmpeg_path):
    """Return ffmpeg version string or None."""
    try:
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.splitlines()[0] if result.returncode == 0 else None
    except Exception:
        return None
