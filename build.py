"""build standalone exe with pyinstaller. output lands in dist/"""

import shutil
import subprocess
import sys
from pathlib import Path

NAME = "riptide"
DIST = Path("dist")
BUILD = Path("build")


def clean():
    for d in (DIST, BUILD):
        if d.exists():
            shutil.rmtree(d)
    spec = Path(f"{NAME}.spec")
    if spec.exists():
        spec.unlink()
    print("cleaned old artifacts")


def build():
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", NAME,
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--collect-all", "yt_dlp",
        "riptide/__main__.py",
    ]
    print(f"running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    print("building riptide...")
    clean()
    build()
    exe = DIST / f"{NAME}.exe"
    if exe.exists():
        mb = exe.stat().st_size / (1024 * 1024)
        print(f"\ndone -> {exe.resolve()} ({mb:.1f} MB)")
    else:
        print("build failed, check output above")
