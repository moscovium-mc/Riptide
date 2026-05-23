import json
import os
import shutil
import subprocess
from pathlib import Path

from riptide._version import __version__ as APP_VERSION

APP_NAME = "Riptide YouTube Downloader"

# user config persists across launches
CONFIG_DIR = Path.home() / ".config" / "riptide"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_DOWNLOAD_DIR = str(Path.home() / "Downloads")

# format strings yt-dlp understands
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

FILENAME_TEMPLATES = {
    "Default": "%(title)s [%(id)s].%(ext)s",
    "Artist - Title": "%(artist)s - %(title)s.%(ext)s",
    "Title Only": "%(title)s.%(ext)s",
    "ID Only": "%(id)s.%(ext)s",
    "Playlist Order": "%(playlist_index)s - %(title)s.%(ext)s",
    "Custom": "",
}

DEFAULTS = {
    "mode": "video",
    "format": "Best",
    "audio_quality": 192,
    "output_dir": DEFAULT_DOWNLOAD_DIR,
    "naming_template": "Default",
    "custom_template": "",
    "embed_metadata": True,
    "ffmpeg_path": "",
    "last_urls": [],
}


def load_settings():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    out = DEFAULTS.copy()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                out.update(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    return out


def save_settings(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except OSError:
        pass


def find_ffmpeg(custom=""):
    if custom and os.path.isfile(custom):
        return custom

    candidates = [
        "ffmpeg",
        str(Path.home() / "Desktop" / "FFmpeg" / "ffmpeg.exe"),
        str(Path.home() / "Desktop" / "FFmpeg" / "bin" / "ffmpeg.exe"),
        str(Path.home() / "Desktop" / "FFmpeg" / "ffmpeg"),
        str(Path.home() / "Desktop" / "FFmpeg" / "bin" / "ffmpeg"),
    ]

    for p in candidates:
        resolved = shutil.which(p) or p
        if os.path.isfile(resolved):
            return resolved
    return None


def get_ffmpeg_version(path):
    try:
        r = subprocess.run([path, "-version"], capture_output=True, text=True, timeout=5)
        return r.stdout.splitlines()[0] if r.returncode == 0 else None
    except Exception:
        return None
