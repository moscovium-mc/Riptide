from riptide._version import __version__


def main():
    import sys
    from PySide6.QtWidgets import QApplication
    from riptide.window import MainWindow

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
