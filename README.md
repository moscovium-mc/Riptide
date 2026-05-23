# Riptide YouTube Downloader V1.0.0

fast youtube video/audio downloader with ffmpeg support. built on top of yt-dlp with a clean PySide6 GUI.

also doubles as a media trimmer - cut videos and audio files using ffmpeg without leaving the app.

## what it does

- download videos or extract audio (mp3, aac, flac, opus, wav, m4a)
- auto-embed metadata + cover art into output files
- preview title, artist, duration, and thumbnail before downloading
- queue multiple urls for sequential downloads
- drag urls from browser directly into the window
- pick filename patterns from presets or roll your own
- trim/cut local media files with ffmpeg (copy codecs, re-encode, or audio-only)
- settings stick around between sessions
- hunts down ffmpeg automatically so audio conversion just works

## requirements

- python 3.10+ (source only)
- ffmpeg (needed for audio extraction, metadata embedding, and media trimming)

## install

### standalone exe (windows)
grab `riptide.exe` from the releases page. no install needed.

### from source
```
git clone https://github.com/moscovium-mc/riptide.git
cd riptide
pip install -r requirements.txt
python -m riptide
```

### build your own exe
```
pip install pyinstaller
python build.py
```
exe drops into `dist/riptide.exe`

## ffmpeg setup

riptide looks for ffmpeg in these spots:
- system `PATH`
- `~/Desktop/FFmpeg/ffmpeg.exe`
- `~/Desktop/FFmpeg/bin/ffmpeg.exe`

grab it from https://ffmpeg.org/download.html

## usage

### download
1. paste a video/playlist url
2. pick video or audio mode
3. choose format/quality
4. hit **Fetch Info** to preview metadata (optional)
5. **Add** to queue or download straight away
6. **START**

### trim / cut media
1. **Tools > Trim / Cut Media**
2. browse for a video or audio file
3. click **Load Info** to probe duration and codec info
4. set start and end times (HH:MM:SS)
5. pick a mode:
   - **Copy codecs** - fast, no quality loss, stream copy
   - **Re-encode** - h.264 video + aac audio, wide compatibility
   - **Audio only** - strips video, encodes to selected format
6. hit **TRIM**

## license

MIT
