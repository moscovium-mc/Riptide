import os
import sys
from pathlib import Path
from urllib.request import urlopen

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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

from riptide.config import (
    APP_NAME,
    APP_VERSION,
    AUDIO_FORMATS,
    CONFIG_FILE,
    DEFAULT_DOWNLOAD_DIR,
    FILENAME_TEMPLATES,
    VIDEO_FORMATS,
    find_ffmpeg,
    get_ffmpeg_version,
    load_settings,
    save_settings,
)
from riptide.downloader import DownloadWorker, MetadataFetcher
from riptide.ffmpeg_tool import TrimDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = load_settings()
        self.meta_thread = None
        self.dl_thread = None
        self.queue = list(self.cfg.get("last_urls", []))
        self._build_ui()
        self._restore_settings()
        self._probe_ffmpeg()

    # ui
    def _build_ui(self):
        self.setWindowTitle(f"{APP_NAME} V{APP_VERSION}")
        self.setAcceptDrops(True)
        self.setFixedSize(560, 620)
        self._menubar()

        central = QWidget()
        self.setCentralWidget(central)
        lay = QVBoxLayout(central)
        lay.setSpacing(8)
        lay.setContentsMargins(14, 10, 14, 10)

        row = QHBoxLayout()
        row.setSpacing(6)
        self.url_lbl = self._label("URL:")
        self.url_inp = QLineEdit()
        self.url_inp.setPlaceholderText("https://www.youtube.com/watch?v=...")
        self.add_btn = QPushButton("Add")
        self.add_btn.setFixedWidth(50)
        self.add_btn.clicked.connect(self._add_queue)
        self.fetch_btn = QPushButton("Fetch Info")
        self.fetch_btn.setFixedWidth(70)
        self.fetch_btn.clicked.connect(self._fetch_meta)
        row.addWidget(self.url_lbl)
        row.addWidget(self.url_inp)
        row.addWidget(self.add_btn)
        row.addWidget(self.fetch_btn)
        lay.addLayout(row)

        self.preview = QWidget()
        self.preview.setVisible(False)
        prev_lay = QHBoxLayout(self.preview)
        prev_lay.setContentsMargins(0, 4, 0, 4)
        prev_lay.setSpacing(10)

        self.thumb = QLabel()
        self.thumb.setFixedSize(80, 60)
        self.thumb.setStyleSheet("background:#333; border:1px solid #555;")
        self.thumb.setAlignment(Qt.AlignCenter)

        info = QVBoxLayout()
        info.setSpacing(2)
        self.meta_title = QLabel()
        self.meta_title.setWordWrap(True)
        self.meta_title.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.meta_artist = QLabel()
        self.meta_artist.setFont(QFont("Segoe UI", 8))
        self.meta_dur = QLabel()
        self.meta_dur.setFont(QFont("Segoe UI", 8))
        for w in (self.meta_title, self.meta_artist, self.meta_dur):
            info.addWidget(w)
        info.addStretch()

        prev_lay.addWidget(self.thumb)
        prev_lay.addLayout(info)
        lay.addWidget(self.preview)

        q_row = QHBoxLayout()
        q_row.setSpacing(6)
        self.q_lbl = self._label("Queue:")
        self.q_list = QListWidget()
        self.q_list.setMaximumHeight(80)
        self.q_list.setAlternatingRowColors(True)
        self._refresh_queue()
        self.q_rm = QPushButton("Remove")
        self.q_rm.setFixedWidth(60)
        self.q_rm.clicked.connect(self._rm_queue)
        q_row.addWidget(self.q_lbl)
        q_row.addWidget(self.q_list)
        q_row.addWidget(self.q_rm)
        lay.addLayout(q_row)

        lay.addWidget(self._sep())

        mode = QHBoxLayout()
        mode.setSpacing(6)
        self.mode_lbl = self._label("Mode:")
        self.mode_vid = QRadioButton("Video")
        self.mode_aud = QRadioButton("Audio")
        self.mode_vid.setChecked(True)
        self.mode_vid.toggled.connect(self._switch_mode)
        mode.addWidget(self.mode_lbl)
        mode.addWidget(self.mode_vid)
        mode.addWidget(self.mode_aud)
        mode.addStretch()
        lay.addLayout(mode)

        fmt = QHBoxLayout()
        fmt.setSpacing(6)
        self.fmt_lbl = self._label("Format:")
        self.fmt_combo = QComboBox()
        self.q_lbl2 = QLabel("Quality:")
        self.q_spin = QSpinBox()
        self.q_spin.setRange(0, 320)
        self.q_spin.setValue(192)
        self.q_spin.setSuffix(" kbps")
        self.q_spin.setFixedWidth(80)
        self.q_lbl2.setVisible(False)
        self.q_spin.setVisible(False)
        self._fill_formats()
        fmt.addWidget(self.fmt_lbl)
        fmt.addWidget(self.fmt_combo)
        fmt.addWidget(self.q_lbl2)
        fmt.addWidget(self.q_spin)
        fmt.addStretch()
        lay.addLayout(fmt)

        tmpl = QHBoxLayout()
        tmpl.setSpacing(6)
        self.tmpl_lbl = self._label("Naming:")
        self.tmpl_combo = QComboBox()
        self.tmpl_combo.addItems(FILENAME_TEMPLATES.keys())
        self.tmpl_combo.currentTextChanged.connect(self._tmpl_changed)
        self.custom_tmpl = QLineEdit()
        self.custom_tmpl.setPlaceholderText("%(artist)s - %(title)s.%(ext)s")
        self.custom_tmpl.setVisible(False)
        tmpl.addWidget(self.tmpl_lbl)
        tmpl.addWidget(self.tmpl_combo)
        tmpl.addWidget(self.custom_tmpl)
        tmpl.addStretch()
        lay.addLayout(tmpl)

        out = QHBoxLayout()
        out.setSpacing(6)
        self.out_lbl = self._label("Output:")
        self.out_inp = QLineEdit()
        self.out_inp.setText(DEFAULT_DOWNLOAD_DIR)
        self.out_inp.setReadOnly(True)
        self.browse_btn = QPushButton("...")
        self.browse_btn.setFixedWidth(30)
        self.browse_btn.clicked.connect(self._pick_dir)
        out.addWidget(self.out_lbl)
        out.addWidget(self.out_inp)
        out.addWidget(self.browse_btn)
        lay.addLayout(out)

        opts = QHBoxLayout()
        opts.setSpacing(6)
        self.embed_cb = QCheckBox("Embed metadata & cover art")
        self.embed_cb.setChecked(True)
        self.ffmpeg_st = QLabel("FFmpeg: checking...")
        self.ffmpeg_st.setFont(QFont("Segoe UI", 8))
        opts.addWidget(self.embed_cb)
        opts.addWidget(self.ffmpeg_st)
        opts.addStretch()
        lay.addLayout(opts)

        lay.addWidget(self._sep())

        self.prog = QProgressBar()
        self.prog.setMinimumHeight(20)
        lay.addWidget(self.prog)

        self.status = QLabel("Ready")
        self.status.setIndent(4)
        lay.addWidget(self.status)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(100)
        self.log.setFont(QFont("Consolas" if sys.platform == "win32" else "Monospace", 8))
        lay.addWidget(self.log)

        btns = QHBoxLayout()
        btns.addStretch()
        self.start_btn = QPushButton("START")
        self.start_btn.setFixedWidth(90)
        self.start_btn.setMinimumHeight(28)
        self.start_btn.clicked.connect(self._start_dl)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedWidth(90)
        self.cancel_btn.setMinimumHeight(28)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_dl)
        self.close_btn = QPushButton("CLOSE")
        self.close_btn.setFixedWidth(90)
        self.close_btn.setMinimumHeight(28)
        self.close_btn.clicked.connect(self._save_and_quit)
        btns.addWidget(self.start_btn)
        btns.addWidget(self.cancel_btn)
        btns.addWidget(self.close_btn)
        lay.addLayout(btns)

    @staticmethod
    def _label(text):
        l = QLabel(text)
        l.setFixedWidth(80)
        return l

    @staticmethod
    def _sep():
        s = QLabel()
        s.setStyleSheet("background:#a0a0a0; max-height:1px; min-height:1px;")
        return s

    def _log(self, msg):
        self.log.append(msg)

    def _tmpl(self):
        sel = self.tmpl_combo.currentText()
        if sel == "Custom":
            return self.custom_tmpl.text().strip() or FILENAME_TEMPLATES["Default"]
        return FILENAME_TEMPLATES.get(sel, FILENAME_TEMPLATES["Default"])

    # settings
    def _restore_settings(self):
        c = self.cfg
        if c.get("mode") == "audio":
            self.mode_aud.setChecked(True)
        self.fmt_combo.setCurrentText(c.get("format", "Best"))
        self.q_spin.setValue(c.get("audio_quality", 192))
        self.out_inp.setText(c.get("output_dir", DEFAULT_DOWNLOAD_DIR))
        self.tmpl_combo.setCurrentText(c.get("naming_template", "Default"))
        self.custom_tmpl.setText(c.get("custom_template", ""))
        self.embed_cb.setChecked(c.get("embed_metadata", True))

    def _persist(self):
        self.cfg.update({
            "mode": "audio" if self.mode_aud.isChecked() else "video",
            "format": self.fmt_combo.currentText(),
            "audio_quality": self.q_spin.value(),
            "output_dir": self.out_inp.text(),
            "naming_template": self.tmpl_combo.currentText(),
            "custom_template": self.custom_tmpl.text(),
            "embed_metadata": self.embed_cb.isChecked(),
            "last_urls": self.queue,
        })
        save_settings(self.cfg)

    def _save_and_quit(self):
        self.close()

    def closeEvent(self, event):
        if self.dl_thread and self.dl_thread.isRunning():
            self.dl_thread.kill()
            self.dl_thread.wait(2000)
        if self.meta_thread and self.meta_thread.isRunning():
            self.meta_thread.wait(2000)
        self._persist()
        super().closeEvent(event)

    def _probe_ffmpeg(self):
        path = find_ffmpeg(self.cfg.get("ffmpeg_path", ""))
        if path:
            ver = get_ffmpeg_version(path)
            self.ffmpeg_st.setText(f"FFmpeg: ok ({ver or 'found'})")
            self.ffmpeg_st.setStyleSheet("color:#2a7b2a;")
            self.cfg["ffmpeg_path"] = path
            save_settings(self.cfg)
        else:
            self.ffmpeg_st.setText("FFmpeg: not found")
            self.ffmpeg_st.setStyleSheet("color:#b03030;")
            self.embed_cb.setEnabled(False)

    # menu
    def _menubar(self):
        mb = self.menuBar()
        f = mb.addMenu("&File")
        f.addAction("Settings...").triggered.connect(lambda: QMessageBox.information(self, "Settings", f"Config lives at:\n{CONFIG_FILE}"))
        f.addSeparator()
        f.addAction("Exit").triggered.connect(self._save_and_quit)

        t = mb.addMenu("&Tools")
        t.addAction("Trim / Cut Media").triggered.connect(self._open_trim)

        h = mb.addMenu("&Help")
        h.addAction("FFmpeg Setup").triggered.connect(self._ffmpeg_help)
        h.addSeparator()
        h.addAction("About").triggered.connect(self._about)

    def _ffmpeg_help(self):
        QMessageBox.information(self, "FFmpeg Setup",
            "ffmpeg is needed for audio extraction and metadata embedding.\n\n"
            "1. grab it from https://ffmpeg.org/download.html\n"
            "2. drop ffmpeg.exe on your Desktop or add to PATH\n"
            "3. app picks it up automatically on startup\n\n"
            f"current: {self.ffmpeg_st.text()}")

    def _about(self):
        QMessageBox.about(self, "About",
            f"{APP_NAME} V{APP_VERSION}\n\n"
            "fast youtube video/audio downloader with ffmpeg support.\n"
            "queue, drag-drop, metadata preview, auto-embedding.\n\n"
            "built with PySide6 + yt-dlp.")

    def _open_trim(self):
        ffmpeg = self.cfg.get("ffmpeg_path", "")
        if not ffmpeg:
            ffmpeg = find_ffmpeg()
        if not ffmpeg:
            QMessageBox.warning(self, "Trim", "FFmpeg not found.\nInstall FFmpeg to use the trim tool.")
            return
        TrimDialog(self, ffmpeg).exec()

    # queue
    def _add_queue(self):
        url = self.url_inp.text().strip()
        if not url:
            return
        self.queue.append(url)
        self._refresh_queue()
        self.url_inp.clear()

    def _rm_queue(self):
        idx = self.q_list.currentRow()
        if idx >= 0:
            self.queue.pop(idx)
            self._refresh_queue()

    def _refresh_queue(self):
        self.q_list.clear()
        for u in self.queue:
            self.q_list.addItem(u)

    # formats
    def _switch_mode(self):
        self._fill_formats()

    def _fill_formats(self):
        self.fmt_combo.clear()
        if self.mode_vid.isChecked():
            for n in VIDEO_FORMATS:
                self.fmt_combo.addItem(n)
            self.q_lbl2.setVisible(False)
            self.q_spin.setVisible(False)
        else:
            for n in AUDIO_FORMATS:
                self.fmt_combo.addItem(n)
            self.q_lbl2.setVisible(True)
            self.q_spin.setVisible(True)

    def _tmpl_changed(self, name):
        self.custom_tmpl.setVisible(name == "Custom")

    def _pick_dir(self):
        p = QFileDialog.getExistingDirectory(self, "Select Output Directory", self.out_inp.text())
        if p:
            self.out_inp.setText(p)

    def _fetch_meta(self):
        if self.meta_thread and self.meta_thread.isRunning():
            return
        url = self.url_inp.text().strip()
        if not url:
            QMessageBox.warning(self, APP_NAME, "enter a URL first.")
            return

        self.fetch_btn.setEnabled(False)
        self.fetch_btn.setText("Fetching...")
        self.preview.setVisible(False)

        self.meta_thread = MetadataFetcher(url)
        self.meta_thread.done.connect(self._meta_ok)
        self.meta_thread.fail.connect(self._meta_fail)
        self.meta_thread.start()

    def _meta_ok(self, info):
        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText("Fetch Info")
        self.preview.setVisible(True)

        self.meta_title.setText(info.get("title", "unknown"))
        self.meta_artist.setText(info.get("artist") or info.get("uploader", "unknown"))
        dur = info.get("duration", 0)
        m, s = divmod(int(dur), 60)
        self.meta_dur.setText(f"{m}:{s:02d}")

        thumb_url = info.get("thumbnail")
        if thumb_url:
            try:
                data = urlopen(thumb_url, timeout=10).read()
                pm = QPixmap()
                if pm.loadFromData(data):
                    self.thumb.setPixmap(pm.scaled(80, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                else:
                    self.thumb.setText("no thumb")
            except Exception:
                self.thumb.setText("no thumb")
        else:
            self.thumb.setText("no thumb")

        self._log(f"fetched: {info.get('title')}")

    def _meta_fail(self, msg):
        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText("Fetch Info")
        self._log(f"meta fetch failed: {msg}")

    # download
    def _start_dl(self):
        if self.dl_thread and self.dl_thread.isRunning():
            return
        urls = list(self.queue)
        cur = self.url_inp.text().strip()
        if cur:
            urls.append(cur)
        if not urls:
            QMessageBox.warning(self, APP_NAME, "add at least one URL to the queue.")
            return

        out = self.out_inp.text()
        if not os.path.isdir(out):
            QMessageBox.warning(self, APP_NAME, "output directory doesn't exist.")
            return

        self.start_btn.setEnabled(False)
        self.start_btn.setText("DOWNLOADING...")
        self.cancel_btn.setEnabled(True)
        self.prog.setValue(0)
        self.status.setText("starting...")
        self.log.clear()

        opts = {
            "outtmpl": str(Path(out) / self._tmpl()),
            "quiet": True,
            "no_warnings": True,
        }

        if self.cfg.get("ffmpeg_path"):
            opts["ffmpeg_location"] = self.cfg["ffmpeg_path"]

        if self.embed_cb.isChecked():
            opts["writethumbnail"] = True
            opts["embedthumbnail"] = True
            opts["addmetadata"] = True

        if self.mode_aud.isChecked():
            ext, _ = AUDIO_FORMATS[self.fmt_combo.currentText()]
            opts["format"] = "bestaudio/best"
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": ext,
                "preferredquality": self.q_spin.value(),
            }]
        else:
            opts["format"] = VIDEO_FORMATS[self.fmt_combo.currentText()]

        self.dl_thread = DownloadWorker(urls, opts)
        self.dl_thread.progress.connect(self._on_progress)
        self.dl_thread.item_done.connect(self._item_done)
        self.dl_thread.queue_done.connect(self._queue_done)
        self.dl_thread.start()

    def _cancel_dl(self):
        if self.dl_thread and self.dl_thread.isRunning():
            self.dl_thread.kill()
            self.status.setText("cancelling...")
            self._log("cancelling download after current item...")

    def _on_progress(self, d):
        st = d.get("status")
        if st == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            done = d.get("downloaded_bytes", 0)
            if total > 0:
                pct = int(done / total * 100)
                self.prog.setValue(pct)
                spd = d.get("speed", 0) or 0
                spd_s = f"{spd / 1024 / 1024:.2f} MB/s" if spd else "..."
                self.status.setText(f"downloading... {pct}% - {spd_s}")
        elif st == "finished":
            self.status.setText("processing...")
            self.prog.setValue(100)

    def _item_done(self, url, ok, msg):
        self._log(f"{'ok' if ok else 'fail'}: {url[:60]}...")

    def _queue_done(self):
        self.start_btn.setEnabled(True)
        self.start_btn.setText("START")
        self.cancel_btn.setEnabled(False)
        self.status.setText("queue complete.")
        self._log("all downloads finished.")

    # drag & drop
    def dragEnterEvent(self, ev: QDragEnterEvent):
        if ev.mimeData().hasText():
            ev.acceptProposedAction()

    def dropEvent(self, ev: QDropEvent):
        txt = ev.mimeData().text().strip()
        if txt.startswith("http"):
            self.url_inp.setText(txt)
