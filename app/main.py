from __future__ import annotations

import os
import sys

from PySide6.QtWidgets import QApplication

from app.config import APP_NAME, resource_path


def _gpu_enabled() -> bool:
    return os.environ.get("WHISPER_WATCH_USE_GPU", "0").strip().lower() in {"1", "true", "yes", "on"}


if not _gpu_enabled():
    # Disable CUDA probing by default so the app runs on machines without
    # GPU runtime libraries (cublas/cudnn).
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")

from app.ui.main_window import MainWindow


def load_stylesheet() -> str:
    stylesheet_path = resource_path("ui", "styles.qss")
    if not stylesheet_path.exists():
        return ""
    return stylesheet_path.read_text(encoding="utf-8")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyleSheet(load_stylesheet())

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
