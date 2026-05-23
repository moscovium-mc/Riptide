import json
import os
import re
import subprocess
from pathlib import Path

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QFont, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)
from PySide6.QtCore import QRegularExpression


class FfprobeWorker(QThread):
    done = Signal(dict)
    fail = Signal(str)

    def __init__(self, probe_bin, file_path):
        super().__init__()
        self.probe_bin = probe_bin
        self.file_path = file_path

    def run(self):
        try:
            r = subprocess.run(
                [self.probe_bin, "-v", "quiet", "-print_format", "json",
                 "-show_format", "-show_streams", self.file_path],
                capture_output=True, text=True, timeout=30,
            )
            self.done.emit(json.loads(r.stdout))
        except Exception as e:
            self.fail.emit(str(e))


class TrimWorker(QThread):
    progress = Signal(int)
    done = Signal(bool, str)

    def __init__(self, ffmpeg_bin, args, duration=0):
        super().__init__()
        self.ffmpeg_bin = ffmpeg_bin
        self.args = args
        self.duration = duration
        self._alive = True

    def run(self):
        try:
            proc = subprocess.Popen(
                [self.ffmpeg_bin] + self.args,
                stderr=subprocess.PIPE, text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            pat = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")
            for line in proc.stderr:
                if not self._alive:
                    proc.kill()
                    proc.wait()
                    break
                m = pat.search(line)
                if m and self.duration > 0:
                    secs = int(m.group(1))*3600 + int(m.group(2))*60 + float(m.group(3))
                    self.progress.emit(min(int(secs / self.duration * 100), 99))
            proc.wait()
            if proc.returncode == 0 and self._alive:
                self.progress.emit(100)
                self.done.emit(True, "ok")
            elif self._alive:
                err = proc.stderr.read() if proc.stderr else "unknown error"
                self.done.emit(False, err)
        except Exception as e:
            self.done.emit(False, str(e))

    def kill(self):
        self._alive = False


def _find_ffprobe(ffmpeg_path):
    p = Path(ffmpeg_path)
    if p.parent == Path("."):
        return "ffprobe"
    guess = p.parent / f"ffprobe{p.suffix}"
    return str(guess) if guess.exists() else "ffprobe"


TIME_RE = r"^\d{1,3}:\d{2}:\d{2}$"
_time_val = QRegularExpressionValidator(QRegularExpression(TIME_RE))


class TrimDialog(QDialog):
    def __init__(self, parent, ffmpeg_path):
        super().__init__(parent)
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = _find_ffprobe(ffmpeg_path)
        self.info_worker = None
        self.trim_worker = None
        self.file_info = None
        self._dur_secs = 0
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Trim / Cut Media")
        self.setFixedSize(480, 320)

        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        lay.setContentsMargins(14, 10, 14, 10)

        in_row = QHBoxLayout()
        in_row.setSpacing(6)
        self.in_lbl = QLabel("Input:")
        self.in_lbl.setFixedWidth(70)
        self.in_path = QLineEdit()
        self.in_path.setPlaceholderText("select a video or audio file...")
        self.in_btn = QPushButton("Browse")
        self.in_btn.setFixedWidth(60)
        self.in_btn.clicked.connect(self._pick_input)
        self.probe_btn = QPushButton("Load Info")
        self.probe_btn.setFixedWidth(70)
        self.probe_btn.setEnabled(False)
        self.probe_btn.clicked.connect(self._load_info)
        in_row.addWidget(self.in_lbl)
        in_row.addWidget(self.in_path)
        in_row.addWidget(self.in_btn)
        in_row.addWidget(self.probe_btn)
        lay.addLayout(in_row)

        self.info_lbl = QLabel("Duration: --")
        self.info_lbl.setFont(QFont("Segoe UI", 8))
        lay.addWidget(self.info_lbl)

        self._make_row(lay, "Start:", "00:00:00", "start")
        self._make_row(lay, "End:", "00:00:00", "end")

        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        self.mode_lbl = QLabel("Mode:")
        self.mode_lbl.setFixedWidth(70)
        self.mode_cb = QComboBox()
        self.mode_cb.addItems([
            "Copy codecs (fast)",
            "Re-encode (compatible)",
            "Audio only",
        ])
        mode_row.addWidget(self.mode_lbl)
        mode_row.addWidget(self.mode_cb)
        mode_row.addStretch()
        lay.addLayout(mode_row)

        out_row = QHBoxLayout()
        out_row.setSpacing(6)
        self.out_lbl = QLabel("Output:")
        self.out_lbl.setFixedWidth(70)
        self.out_path = QLineEdit()
        self.out_path.setPlaceholderText("auto-filled on input select")
        self.out_btn = QPushButton("Browse")
        self.out_btn.setFixedWidth(60)
        self.out_btn.clicked.connect(self._pick_output)
        out_row.addWidget(self.out_lbl)
        out_row.addWidget(self.out_path)
        out_row.addWidget(self.out_btn)
        lay.addLayout(out_row)

        lay.addSpacing(6)

        self.trim_btn = QPushButton("TRIM")
        self.trim_btn.setMinimumHeight(28)
        self.trim_btn.clicked.connect(self._start_trim)
        lay.addWidget(self.trim_btn)

        self.trim_prog = QProgressBar()
        self.trim_prog.setMinimumHeight(18)
        lay.addWidget(self.trim_prog)

        self.trim_st = QLabel("select a file to begin")
        self.trim_st.setIndent(4)
        lay.addWidget(self.trim_st)

    def _make_row(self, parent, label, placeholder, attr):
        row = QHBoxLayout()
        row.setSpacing(6)
        lbl = QLabel(label)
        lbl.setFixedWidth(70)
        inp = QLineEdit()
        inp.setPlaceholderText(placeholder)
        inp.setMaxLength(10)
        inp.setFixedWidth(100)
        inp.setValidator(_time_val)
        setattr(self, f"{attr}_inp", inp)
        row.addWidget(lbl)
        row.addWidget(inp)
        row.addStretch()
        parent.addLayout(row)

    def _pick_input(self):
        p, _ = QFileDialog.getOpenFileName(
            self, "Select Media File", "",
            "Media (*.mp4 *.mkv *.avi *.mov *.webm *.flv *.mp3 *.aac *.flac *.opus *.wav *.m4a);;All (*.*)"
        )
        if p:
            self.in_path.setText(p)
            self.probe_btn.setEnabled(True)
            stem = Path(p).stem
            self.out_path.setText(str(Path(p).parent / f"{stem}_trimmed{Path(p).suffix}"))

    def _pick_output(self):
        p, _ = QFileDialog.getSaveFileName(
            self, "Save As", self.out_path.text() or "",
            "Media (*.mp4 *.mkv *.avi *.mov *.mp3 *.aac *.flac *.opus *.wav *.m4a);;All (*.*)"
        )
        if p:
            self.out_path.setText(p)

    def _load_info(self):
        path = self.in_path.text().strip()
        if not path or not os.path.isfile(path):
            QMessageBox.warning(self, "Trim", "select a valid input file")
            return
        self.probe_btn.setEnabled(False)
        self.probe_btn.setText("Loading...")
        self.info_lbl.setText("Duration: probing...")
        self.info_worker = FfprobeWorker(self.ffprobe_path, path)
        self.info_worker.done.connect(self._info_loaded)
        self.info_worker.fail.connect(self._info_failed)
        self.info_worker.start()

    def _info_loaded(self, data):
        self.probe_btn.setEnabled(True)
        self.probe_btn.setText("Load Info")
        self.file_info = data
        fmt = data.get("format", {})
        dur = float(fmt.get("duration", 0))
        self._dur_secs = dur
        h, r = divmod(int(dur), 3600)
        m, s = divmod(r, 60)
        fmt_name = fmt.get("format_name", "?")
        self.info_lbl.setText(f"Duration: {h:02d}:{m:02d}:{s:02d}  |  {fmt_name}")
        self.end_inp.setText(f"{h:02d}:{m:02d}:{s:02d}")
        self.trim_st.setText("ready")

    def _info_failed(self, msg):
        self.probe_btn.setEnabled(True)
        self.probe_btn.setText("Load Info")
        self.info_lbl.setText("Duration: failed to probe")
        self.trim_st.setText(f"probe failed: {msg}")

    def _parse_time(self, text):
        parts = text.strip().split(":")
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

    def _start_trim(self):
        inp = self.in_path.text().strip()
        out = self.out_path.text().strip()
        if not inp or not os.path.isfile(inp):
            QMessageBox.warning(self, "Trim", "select a valid input file")
            return
        if not out:
            QMessageBox.warning(self, "Trim", "specify an output file")
            return

        try:
            start = self._parse_time(self.start_inp.text())
            end = self._parse_time(self.end_inp.text())
        except (ValueError, IndexError):
            QMessageBox.warning(self, "Trim", "invalid time format (use HH:MM:SS)")
            return

        if end <= start:
            QMessageBox.warning(self, "Trim", "end must be after start")
            return

        dur = end - start
        mode = self.mode_cb.currentIndex()

        args = ["-y", "-ss", str(start), "-i", inp]
        if mode == 0:
            args += ["-t", str(dur), "-c", "copy", "-map", "0"]
        elif mode == 1:
            args += ["-t", str(dur), "-c:v", "libx264", "-preset", "fast",
                     "-c:a", "aac", "-b:a", "192k", "-map", "0"]
        else:
            ext = Path(out).suffix.lower()
            if ext in (".mp3",):
                codec = "libmp3lame"
                bitrate = "-b:a", "192k"
            elif ext in (".aac", ".m4a"):
                codec = "aac"
                bitrate = "-b:a", "192k"
            elif ext in (".flac",):
                codec = "flac"
                bitrate = "-compression_level", "5"
            elif ext in (".opus",):
                codec = "libopus"
                bitrate = "-b:a", "128k"
            elif ext in (".wav",):
                codec = "pcm_s16le"
                bitrate = ()
            else:
                codec = "libmp3lame"
                bitrate = "-b:a", "192k"
            args += ["-t", str(dur), "-vn"]
            args += ["-c:a", codec]
            if bitrate:
                args += list(bitrate)
            args += ["-map", "0:a?"]

        args.append(out)

        self.trim_btn.setEnabled(False)
        self.trim_btn.setText("TRIMMING...")
        self.trim_prog.setValue(0)
        self.trim_st.setText("trimming...")

        self.trim_worker = TrimWorker(self.ffmpeg_path, args, dur)
        self.trim_worker.progress.connect(self.trim_prog.setValue)
        self.trim_worker.done.connect(self._trim_done)
        self.trim_worker.start()

    def _trim_done(self, ok, msg):
        self.trim_btn.setEnabled(True)
        self.trim_btn.setText("TRIM")
        if ok:
            self.trim_prog.setValue(100)
            self.trim_st.setText("done")
            QMessageBox.information(self, "Trim", f"saved:\n{self.out_path.text()}")
        else:
            self.trim_st.setText("trim failed")
            QMessageBox.warning(self, "Trim", f"trim failed:\n{msg[:300]}")

    def closeEvent(self, event):
        if self.trim_worker and self.trim_worker.isRunning():
            self.trim_worker.kill()
            self.trim_worker.wait(2000)
        if self.info_worker and self.info_worker.isRunning():
            self.info_worker.wait(2000)
        super().closeEvent(event)
