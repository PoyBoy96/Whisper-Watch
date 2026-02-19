from __future__ import annotations

import sys
from pathlib import Path

APP_NAME = "Whisper Watch"
APP_ORG = "WhisperWatch"
APP_REPO_URL = "https://github.com/PoyBoy96/Whisper-Watch.git"
UPDATER_USER_AGENT = "Whisper-Watch-Updater"
DEFAULT_MODEL_NAME = "large-v3"
SRT_EDITOR_URL = "https://matthewpenkala.com/srt-editor"


def resource_path(*relative_parts: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).joinpath(*relative_parts)

    app_dir = Path(__file__).resolve().parent
    app_scoped = app_dir.joinpath(*relative_parts)
    if app_scoped.exists():
        return app_scoped

    project_root = app_dir.parent
    return project_root.joinpath(*relative_parts)
