"""yt-dlp downloader wrapper with thread-safe progress reporting."""

import threading
from pathlib import Path

import yt_dlp


class Downloader:
    """Wraps yt-dlp with callback-based progress reporting."""

    def __init__(self):
        self._running = False
        self._thread = None

    @property
    def running(self):
        return self._running

    def download(self, url, opts, hooks, on_done=None, on_error=None):
        """Start download in background thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._run, args=(url, opts, hooks, on_done, on_error), daemon=True
        )
        self._thread.start()

    def cancel(self):
        """Signal cancellation (yt-dlp checks this internally)."""
        self._running = False

    def _run(self, url, opts, hooks, on_done, on_error):
        try:
            ydl_opts = {
                **opts,
                "progress_hooks": [hooks.get("progress", lambda d: None)],
                "postprocessor_hooks": [hooks.get("postprocess", lambda d: None)],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            if self._running and on_done:
                on_done()
        except Exception as e:
            if self._running and on_error:
                on_error(str(e))
        finally:
            self._running = False
