# yt-dlp GUI

A modern, minimalist GUI for [yt-dlp](https://github.com/yt-dlp/yt-dlp) built with PySide6.

## Features

- **Video & Audio Downloads**: Select quality, format, and output directory
- **Metadata Embedding**: Auto-embed cover art, title, artist, and more into MP3/MP4/M4A
- **Metadata Preview**: Fetch title, thumbnail, and duration before downloading
- **Download Queue**: Add multiple URLs and download them sequentially
- **Drag & Drop**: Drag URLs from your browser directly into the app
- **Filename Templates**: Choose from presets or define custom naming patterns
- **Settings Persistence**: Your preferences are saved automatically between sessions
- **FFmpeg Auto-Detection**: Automatically finds FFmpeg on your system

## Requirements

- **Python 3.10+** (for source builds)
- **FFmpeg** (required for audio extraction and metadata embedding)

## Installation

### Option 1: Standalone Executable (Windows)
Download `yt-dlp-gui.exe` from the [Releases](https://github.com/YOUR_USERNAME/yt-dlp-gui/releases) page. No installation required.

### Option 2: From Source
```bash
git clone https://github.com/YOUR_USERNAME/yt-dlp-gui.git
cd yt-dlp-gui
pip install -r requirements.txt
python -m yt_dlp_gui
```

### Option 3: Build Your Own Executable
```bash
pip install pyinstaller
python build.py
```
The executable will be in `dist/yt-dlp-gui.exe`.

## FFmpeg Setup

FFmpeg is required for audio extraction and metadata embedding. The app auto-detects it if:
- It's in your system `PATH`
- Located at `~/Desktop/FFmpeg/ffmpeg.exe` or `~/Desktop/FFmpeg/bin/ffmpeg.exe`

Download FFmpeg from: https://ffmpeg.org/download.html

## Usage

1. Paste a video/playlist URL
2. Choose **Video** or **Audio** mode
3. Select format/quality
4. (Optional) Click **Fetch Info** to preview metadata
5. Click **Add** to queue, or download directly
6. Click **START** to begin downloading

## License

MIT
