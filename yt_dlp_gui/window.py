"""Main application window with Rufus-style layout, queue, drag-drop, menus, and settings."""

import os
import sys
from pathlib import Path
from urllib.request import urlopen

import yt_dlp
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QPixmap, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from yt_dlp_gui.config import (
    APP_NAME,
    APP_VERSION,
    AUDIO_FORMATS,
    CONFIG_DIR,
    DEFAULT_DOWNLOAD_DIR,
    DEFAULT_SETTINGS,
    FILENAME_TEMPLATES,
    VIDEO_FORMATS,
    find_ffmpeg,
    get_ffmpeg_version,
    load_settings,
    save_settings,
)

FILENAME_TEMPLATES = {
    "Default": "%(title)s [%(id)s].%(ext)s",
    "Artist - Title": "%(artist)s - %(title)s.%(ext)s",
    "Title Only": "%(title)s.%(ext)s",
    "ID Only": "%(id)s.%(ext)s",
    "Playlist Order": "%(playlist_index)s - %(title)s.%(ext)s",
    "Custom": "",
}


class MetadataWorker(QThread):
    """Fetches video metadata without downloading."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                info = ydl.extract_info(self.url, download=False)
                self.finished.emit(info)
        except Exception as e:
            self.error.emit(str(e))


class DownloadWorker(QThread):
    """Background thread for yt-dlp downloads."""
    progress = Signal(dict)
    item_finished = Signal(str, bool, str)
    queue_finished = Signal()
    error = Signal(str)

    def __init__(self, urls, opts):
        super().__init__()
        self.urls = urls
        self.opts = opts
        self._running = True

    def run(self):
        def progress_hook(d):
            if self._running:
                self.progress.emit(d)

        for url in self.urls:
            if not self._running:
                break
            try:
                ydl_opts = {
                    **self.opts,
                    "progress_hooks": [progress_hook],
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                if self._running:
                    self.item_finished.emit(url, True, "Done")
            except Exception as e:
                if self._running:
                    self.item_finished.emit(url, False, str(e))

        if self._running:
            self.queue_finished.emit()

    def stop(self):
        self._running = False


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.meta_worker = None
        self.dl_worker = None
        self.current_meta = {}
        self.queue_urls = list(self.settings.get("last_urls", []))
        self._setup_ui()
        self._apply_settings()
        self._check_ffmpeg()

    def _setup_ui(self):
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.setAcceptDrops(True)
        self.setFixedSize(560, 620)
        self._create_menu()

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(14, 10, 14, 10)

        # URL row
        url_row = QHBoxLayout()
        url_row.setSpacing(6)
        self.url_label = QLabel("URL:")
        self.url_label.setFixedWidth(80)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.youtube.com/watch?v=...")
        self.add_btn = QPushButton("Add")
        self.add_btn.setFixedWidth(50)
        self.add_btn.clicked.connect(self._add_to_queue)
        self.fetch_btn = QPushButton("Fetch Info")
        self.fetch_btn.setFixedWidth(70)
        self.fetch_btn.clicked.connect(self._fetch_metadata)
        url_row.addWidget(self.url_label)
        url_row.addWidget(self.url_input)
        url_row.addWidget(self.add_btn)
        url_row.addWidget(self.fetch_btn)
        main_layout.addLayout(url_row)

        # Metadata Preview
        self.preview_box = QWidget()
        self.preview_box.setVisible(False)
        preview_layout = QHBoxLayout(self.preview_box)
        preview_layout.setContentsMargins(0, 4, 0, 4)
        preview_layout.setSpacing(10)

        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(80, 60)
        self.thumb_label.setStyleSheet("background-color: #333; border: 1px solid #555;")
        self.thumb_label.setAlignment(Qt.AlignCenter)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        self.meta_title = QLabel()
        self.meta_title.setWordWrap(True)
        self.meta_title.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.meta_artist = QLabel()
        self.meta_artist.setFont(QFont("Segoe UI", 8))
        self.meta_duration = QLabel()
        self.meta_duration.setFont(QFont("Segoe UI", 8))
        info_layout.addWidget(self.meta_title)
        info_layout.addWidget(self.meta_artist)
        info_layout.addWidget(self.meta_duration)
        info_layout.addStretch()

        preview_layout.addWidget(self.thumb_label)
        preview_layout.addLayout(info_layout)
        main_layout.addWidget(self.preview_box)

        # Queue
        queue_row = QHBoxLayout()
        queue_row.setSpacing(6)
        self.queue_label = QLabel("Queue:")
        self.queue_label.setFixedWidth(80)
        self.queue_list = QListWidget()
        self.queue_list.setMaximumHeight(80)
        self.queue_list.setAlternatingRowColors(True)
        self._refresh_queue_ui()
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.setFixedWidth(60)
        self.remove_btn.clicked.connect(self._remove_from_queue)
        queue_row.addWidget(self.queue_label)
        queue_row.addWidget(self.queue_list)
        queue_row.addWidget(self.remove_btn)
        main_layout.addLayout(queue_row)

        # Separator
        sep = QLabel()
        sep.setStyleSheet("background-color: #a0a0a0; max-height: 1px; min-height: 1px;")
        main_layout.addWidget(sep)

        # Mode row
        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        self.mode_label = QLabel("Mode:")
        self.mode_label.setFixedWidth(80)
        self.mode_video = QRadioButton("Video")
        self.mode_audio = QRadioButton("Audio")
        self.mode_video.setChecked(True)
        self.mode_video.toggled.connect(self._on_mode_changed)
        mode_row.addWidget(self.mode_label)
        mode_row.addWidget(self.mode_video)
        mode_row.addWidget(self.mode_audio)
        mode_row.addStretch()
        main_layout.addLayout(mode_row)

        # Format row
        fmt_row = QHBoxLayout()
        fmt_row.setSpacing(6)
        self.fmt_label = QLabel("Format:")
        self.fmt_label.setFixedWidth(80)
        self.format_combo = QComboBox()
        self.quality_label = QLabel("Quality:")
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(0, 320)
        self.quality_spin.setValue(192)
        self.quality_spin.setSuffix(" kbps")
        self.quality_spin.setFixedWidth(80)
        self.quality_label.setVisible(False)
        self.quality_spin.setVisible(False)
        self._update_formats()
        fmt_row.addWidget(self.fmt_label)
        fmt_row.addWidget(self.format_combo)
        fmt_row.addWidget(self.quality_label)
        fmt_row.addWidget(self.quality_spin)
        fmt_row.addStretch()
        main_layout.addLayout(fmt_row)

        # Filename template row
        tmpl_row = QHBoxLayout()
        tmpl_row.setSpacing(6)
        self.tmpl_label = QLabel("Naming:")
        self.tmpl_label.setFixedWidth(80)
        self.template_combo = QComboBox()
        self.template_combo.addItems(FILENAME_TEMPLATES.keys())
        self.template_combo.currentTextChanged.connect(self._on_template_changed)
        self.custom_tmpl_input = QLineEdit()
        self.custom_tmpl_input.setPlaceholderText("%(artist)s - %(title)s.%(ext)s")
        self.custom_tmpl_input.setVisible(False)
        tmpl_row.addWidget(self.tmpl_label)
        tmpl_row.addWidget(self.template_combo)
        tmpl_row.addWidget(self.custom_tmpl_input)
        tmpl_row.addStretch()
        main_layout.addLayout(tmpl_row)

        # Output row
        out_row = QHBoxLayout()
        out_row.setSpacing(6)
        self.out_label = QLabel("Output:")
        self.out_label.setFixedWidth(80)
        self.output_input = QLineEdit()
        self.output_input.setText(DEFAULT_DOWNLOAD_DIR)
        self.output_input.setReadOnly(True)
        self.browse_btn = QPushButton("...")
        self.browse_btn.setFixedWidth(30)
        self.browse_btn.clicked.connect(self._browse_output)
        out_row.addWidget(self.out_label)
        out_row.addWidget(self.output_input)
        out_row.addWidget(self.browse_btn)
        main_layout.addLayout(out_row)

        # Options row
        opts_row = QHBoxLayout()
        opts_row.setSpacing(6)
        self.embed_check = QCheckBox("Embed metadata & cover art")
        self.embed_check.setChecked(True)
        self.ffmpeg_status = QLabel("FFmpeg: Checking...")
        self.ffmpeg_status.setFont(QFont("Segoe UI", 8))
        opts_row.addWidget(self.embed_check)
        opts_row.addWidget(self.ffmpeg_status)
        opts_row.addStretch()
        main_layout.addLayout(opts_row)

        # Separator
        sep2 = QLabel()
        sep2.setStyleSheet("background-color: #a0a0a0; max-height: 1px; min-height: 1px;")
        main_layout.addWidget(sep2)

        # Progress section
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimumHeight(20)
        main_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready")
        self.status_label.setIndent(4)
        main_layout.addWidget(self.status_label)

        # Log section
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(100)
        self.log_output.setFont(QFont("Consolas" if sys.platform == "win32" else "Monospace", 8))
        main_layout.addWidget(self.log_output)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.download_btn = QPushButton("START")
        self.download_btn.setFixedWidth(90)
        self.download_btn.setMinimumHeight(28)
        self.download_btn.clicked.connect(self._start_download)
        self.cancel_btn = QPushButton("CLOSE")
        self.cancel_btn.setFixedWidth(90)
        self.cancel_btn.setMinimumHeight(28)
        self.cancel_btn.clicked.connect(self._save_and_close)
        btn_row.addWidget(self.download_btn)
        btn_row.addWidget(self.cancel_btn)
        main_layout.addLayout(btn_row)

    def _create_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")
        settings_action = file_menu.addAction("Settings...")
        settings_action.triggered.connect(self._show_settings)
        file_menu.addSeparator()
        exit_action = file_menu.addAction("Exit")
        exit_action.triggered.connect(self._save_and_close)

        help_menu = menubar.addMenu("&Help")
        ffmpeg_action = help_menu.addAction("FFmpeg Setup")
        ffmpeg_action.triggered.connect(self._show_ffmpeg_help)
        help_menu.addSeparator()
        about_action = help_menu.addAction("About")
        about_action.triggered.connect(self._show_about)

    def _apply_settings(self):
        s = self.settings
        if s.get("mode") == "audio":
            self.mode_audio.setChecked(True)
        self.format_combo.setCurrentText(s.get("format", "Best"))
        self.quality_spin.setValue(s.get("audio_quality", 192))
        self.output_input.setText(s.get("output_dir", DEFAULT_DOWNLOAD_DIR))
        self.template_combo.setCurrentText(s.get("naming_template", "Default"))
        self.custom_tmpl_input.setText(s.get("custom_template", ""))
        self.embed_check.setChecked(s.get("embed_metadata", True))

    def _save_current_settings(self):
        self.settings.update({
            "mode": "audio" if self.mode_audio.isChecked() else "video",
            "format": self.format_combo.currentText(),
            "audio_quality": self.quality_spin.value(),
            "output_dir": self.output_input.text(),
            "naming_template": self.template_combo.currentText(),
            "custom_template": self.custom_tmpl_input.text(),
            "embed_metadata": self.embed_check.isChecked(),
            "last_urls": self.queue_urls,
        })
        save_settings(self.settings)

    def _save_and_close(self):
        self._save_current_settings()
        self.close()

    def _check_ffmpeg(self):
        custom = self.settings.get("ffmpeg_path", "")
        path = find_ffmpeg(custom)
        if path:
            ver = get_ffmpeg_version(path)
            self.ffmpeg_status.setText(f"FFmpeg: OK ({ver or 'found'})")
            self.ffmpeg_status.setStyleSheet("color: #2a7b2a;")
            self.settings["ffmpeg_path"] = path
            save_settings(self.settings)
        else:
            self.ffmpeg_status.setText("FFmpeg: Not Found")
            self.ffmpeg_status.setStyleSheet("color: #b03030;")
            self.embed_check.setEnabled(False)

    def _get_template(self):
        sel = self.template_combo.currentText()
        if sel == "Custom":
            return self.custom_tmpl_input.text().strip() or FILENAME_TEMPLATES["Default"]
        return FILENAME_TEMPLATES.get(sel, FILENAME_TEMPLATES["Default"])

    def _on_template_changed(self, name):
        self.custom_tmpl_input.setVisible(name == "Custom")

    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory", self.output_input.text())
        if path:
            self.output_input.setText(path)

    def _on_mode_changed(self):
        self._update_formats()

    def _update_formats(self):
        self.format_combo.clear()
        if self.mode_video.isChecked():
            for name in VIDEO_FORMATS:
                self.format_combo.addItem(name)
            self.quality_label.setVisible(False)
            self.quality_spin.setVisible(False)
        else:
            for name in AUDIO_FORMATS:
                self.format_combo.addItem(name)
            self.quality_label.setVisible(True)
            self.quality_spin.setVisible(True)

    def _add_to_queue(self):
        url = self.url_input.text().strip()
        if not url:
            return
        self.queue_urls.append(url)
        self._refresh_queue_ui()
        self.url_input.clear()

    def _remove_from_queue(self):
        row = self.queue_list.currentRow()
        if row >= 0:
            self.queue_urls.pop(row)
            self._refresh_queue_ui()

    def _refresh_queue_ui(self):
        self.queue_list.clear()
        for url in self.queue_urls:
            self.queue_list.addItem(url)

    def _fetch_metadata(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, APP_NAME, "Please enter a URL first.")
            return

        self.fetch_btn.setEnabled(False)
        self.fetch_btn.setText("Fetching...")
        self.preview_box.setVisible(False)

        self.meta_worker = MetadataWorker(url)
        self.meta_worker.finished.connect(self._on_meta_fetched)
        self.meta_worker.error.connect(self._on_meta_error)
        self.meta_worker.start()

    def _on_meta_fetched(self, info):
        self.current_meta = info
        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText("Fetch Info")
        self.preview_box.setVisible(True)

        self.meta_title.setText(info.get("title", "Unknown Title"))
        self.meta_artist.setText(info.get("artist") or info.get("uploader", "Unknown Artist"))
        duration = info.get("duration", 0)
        mins, secs = divmod(int(duration), 60)
        self.meta_duration.setText(f"{mins}:{secs:02d}")

        thumb_url = info.get("thumbnail")
        if thumb_url:
            try:
                data = urlopen(thumb_url).read()
                pixmap = QPixmap()
                pixmap.loadFromData(data)
                self.thumb_label.setPixmap(pixmap.scaled(80, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            except Exception:
                self.thumb_label.setText("No Thumb")
        else:
            self.thumb_label.setText("No Thumb")

        self._log(f"Fetched: {info.get('title')}")

    def _on_meta_error(self, msg):
        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText("Fetch Info")
        self._log(f"Metadata fetch failed: {msg}")

    def _log(self, msg):
        self.log_output.append(msg)

    def _start_download(self):
        urls = list(self.queue_urls)
        current = self.url_input.text().strip()
        if current:
            urls.append(current)
        if not urls:
            QMessageBox.warning(self, APP_NAME, "Add at least one URL to the queue.")
            return

        output = self.output_input.text()
        if not os.path.isdir(output):
            QMessageBox.warning(self, APP_NAME, "Output directory does not exist.")
            return

        self.download_btn.setEnabled(False)
        self.download_btn.setText("DOWNLOADING...")
        self.progress_bar.setValue(0)
        self.status_label.setText("Starting...")
        self.log_output.clear()

        template = self._get_template()
        opts = {
            "outtmpl": str(Path(output) / template),
            "quiet": True,
            "no_warnings": True,
        }

        if self.settings.get("ffmpeg_path"):
            opts["ffmpeg_location"] = self.settings["ffmpeg_path"]

        if self.embed_check.isChecked():
            opts["writethumbnail"] = True
            opts["embedthumbnail"] = True
            opts["addmetadata"] = True

        if self.mode_audio.isChecked():
            fmt_name = self.format_combo.currentText()
            ext, _ = AUDIO_FORMATS[fmt_name]
            opts["format"] = "bestaudio/best"
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": ext,
                "preferredquality": self.quality_spin.value(),
            }]
        else:
            fmt_name = self.format_combo.currentText()
            opts["format"] = VIDEO_FORMATS[fmt_name]

        self.dl_worker = DownloadWorker(urls, opts)
        self.dl_worker.progress.connect(self._on_progress)
        self.dl_worker.item_finished.connect(self._on_item_finished)
        self.dl_worker.queue_finished.connect(self._on_queue_finished)
        self.dl_worker.error.connect(self._on_error)
        self.dl_worker.start()

    def _on_progress(self, d):
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded = d.get("downloaded_bytes", 0)
            if total > 0:
                pct = int(downloaded / total * 100)
                self.progress_bar.setValue(pct)
                speed = d.get("speed", 0) or 0
                speed_str = f"{speed / 1024 / 1024:.2f} MB/s" if speed else "..."
                self.status_label.setText(f"Downloading... {pct}% - {speed_str}")
        elif status == "finished":
            self.status_label.setText("Processing...")
            self.progress_bar.setValue(100)

    def _on_item_finished(self, url, success, msg):
        self._log(f"{'OK' if success else 'FAIL'}: {url[:60]}...")

    def _on_queue_finished(self):
        self.download_btn.setEnabled(True)
        self.download_btn.setText("START")
        self.status_label.setText("Queue complete.")
        self._log("All downloads finished.")

    def _on_error(self, msg):
        self.download_btn.setEnabled(True)
        self.download_btn.setText("START")
        self.status_label.setText("Error")
        self._log(f"Error: {msg}")
        QMessageBox.critical(self, APP_NAME, msg)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        text = event.mimeData().text().strip()
        if text.startswith("http"):
            self.url_input.setText(text)

    def _show_settings(self):
        QMessageBox.information(self, "Settings", "Settings are automatically saved to:\n" + str(CONFIG_FILE))

    def _show_ffmpeg_help(self):
        msg = (
            "FFmpeg is required for audio extraction and metadata embedding.\n\n"
            "1. Download from https://ffmpeg.org/download.html\n"
            "2. Place ffmpeg.exe in your PATH or on your Desktop\n"
            "3. The app auto-detects it on startup.\n\n"
            f"Current status: {self.ffmpeg_status.text()}"
        )
        QMessageBox.information(self, "FFmpeg Setup", msg)

    def _show_about(self):
        QMessageBox.about(self, "About", f"{APP_NAME} v{APP_VERSION}\n\n"
                          "A modern, minimalist GUI for yt-dlp.\n"
                          "Supports video/audio downloads, metadata embedding, and batch queues.\n\n"
                          "Built with PySide6 & yt-dlp.")
