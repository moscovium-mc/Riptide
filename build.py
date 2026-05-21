"""Build script for PyInstaller. Creates a standalone executable."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

APP_NAME = "yt-dlp-gui"
DIST_DIR = Path("dist")
BUILD_DIR = Path("build")
SPEC_FILE = f"{APP_NAME}.spec"


def clean():
    """Remove old build artifacts."""
    for d in [DIST_DIR, BUILD_DIR]:
        if d.exists():
            shutil.rmtree(d)
    if Path(SPEC_FILE).exists():
        Path(SPEC_FILE).unlink()
    print("Cleaned old build artifacts.")


def build():
    """Run PyInstaller to create the executable."""
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--add-data", "yt_dlp_gui/config.py;yt_dlp_gui",
        "yt_dlp_gui/__main__.py",
    ]
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def main():
    print("Building yt-dlp GUI...")
    clean()
    build()
    exe_path = DIST_DIR / f"{APP_NAME}.exe"
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\nSuccess! Executable created: {exe_path.resolve()}")
        print(f"Size: {size_mb:.1f} MB")
    else:
        print("Build failed. Check output for errors.")


if __name__ == "__main__":
    main()
