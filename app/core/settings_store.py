from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

from app.config import APP_NAME, APP_ORG, DEFAULT_MODEL_NAME


def default_output_dir() -> Path:
    output_dir = Path.home() / "Downloads" / "WhisperWatch"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


class SettingsStore:
    OUTPUT_DIR_KEY = "output_dir"
    MODEL_KEY = "model_name"

    def __init__(self) -> None:
        self._settings = QSettings(APP_ORG, APP_NAME)

    def get_output_dir(self) -> Path:
        raw_value = self._settings.value(self.OUTPUT_DIR_KEY, str(default_output_dir()), type=str)
        path = Path(raw_value).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def set_output_dir(self, output_dir: Path) -> None:
        path = output_dir.expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        self._settings.setValue(self.OUTPUT_DIR_KEY, str(path))

    def get_model_name(self) -> str:
        return self._settings.value(self.MODEL_KEY, DEFAULT_MODEL_NAME, type=str)

    def set_model_name(self, model_name: str) -> None:
        self._settings.setValue(self.MODEL_KEY, model_name)

