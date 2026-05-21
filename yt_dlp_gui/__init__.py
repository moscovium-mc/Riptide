"""yt-dlp GUI - Modern minimalist GUI for yt-dlp."""

__version__ = "2026.05.20"


def main():
    import sys
    from PySide6.QtWidgets import QApplication
    from yt_dlp_gui.window import MainWindow

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
