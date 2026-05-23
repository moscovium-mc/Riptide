import yt_dlp
from PySide6.QtCore import QThread, Signal


class MetadataFetcher(QThread):
    done = Signal(dict)
    fail = Signal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                info = ydl.extract_info(self.url, download=False)
                self.done.emit(info)
        except Exception as e:
            self.fail.emit(str(e))


class DownloadWorker(QThread):
    progress = Signal(dict)
    item_done = Signal(str, bool, str)
    queue_done = Signal()

    def __init__(self, urls, opts):
        super().__init__()
        self.urls = urls
        self.opts = opts
        self._alive = True

    def run(self):
        def hook(d):
            if self._alive:
                self.progress.emit(d)

        for url in self.urls:
            if not self._alive:
                break
            try:
                with yt_dlp.YoutubeDL({**self.opts, "progress_hooks": [hook]}) as ydl:
                    ydl.download([url])
                if self._alive:
                    self.item_done.emit(url, True, "ok")
            except Exception as e:
                if self._alive:
                    self.item_done.emit(url, False, str(e))

        self.queue_done.emit()

    def kill(self):
        self._alive = False
