# Changelog

## 1.0.0 - 2026-05-22

### Added
- initial release - Riptide YouTube Downloader
- youtube video/audio downloads via yt-dlp
- metadata preview (title, artist, duration, thumbnail)
- download queue with sequential processing
- drag-and-drop URL support
- filename templates with custom pattern support
- audio extraction (mp3, aac, flac, opus, wav, m4a)
- metadata + cover art embedding
- persistent settings across sessions
- automatic ffmpeg detection
- ffmpeg trim/cut tool (Tools > Trim / Cut Media)
  - stream copy mode for fast lossless cuts
  - re-encode mode for wide compatibility
  - audio-only extraction with codec selection
  - ffprobe-based duration and format detection
- pyinstaller build script with yt-dlp collect-all

### Changed
- migrated from yt_dlp_gui to riptide package structure

### Fixed
- pyinstaller builds now bundle yt-dlp dynamic extractors via --collect-all
