import sys
from PySide6.QtWidgets import QApplication
from src.ui.main_window import VideoViewer

def main():
    app = QApplication(sys.argv)

    video_path = sys.argv[1] if len(sys.argv) > 1 else None

    window = VideoViewer(video_path=video_path)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

