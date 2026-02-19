from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QColor, QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from app.config import APP_NAME, DEFAULT_MODEL_NAME, SRT_EDITOR_URL, resource_path
from app.core.queue_manager import TranscriptionQueueManager
from app.core.settings_store import SettingsStore
from app.core.srt_service import SrtService
from app.core.transcription_models import JobStatus, TranscriptionJob
from app.core.whisper_service import WhisperService
from app.ui.widgets import DropZoneWidget, GlowButton


def timestamp_for_log(seconds: float) -> str:
    total_seconds = int(max(seconds, 0))
    minutes, secs = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02}:{minutes:02}:{secs:02}"


class MainWindow(QMainWindow):
    MODEL_OPTIONS = [
        ("Large (default)", "large-v3"),
        ("Large v2", "large-v2"),
        ("Medium", "medium"),
        ("Small", "small"),
        ("Base", "base"),
        ("Tiny", "tiny"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1180, 760)
        self.resize(1280, 820)
        self._brand_icon = self._load_brand_icon()
        if not self._brand_icon.isNull():
            self.setWindowIcon(self._brand_icon)

        self._settings = SettingsStore()
        self._queue_manager = TranscriptionQueueManager(
            whisper_service=WhisperService(),
            srt_service=SrtService(),
            parent=self,
        )

        self._active_job_id: str | None = None
        self._latest_srt_path: Path | None = None
        self._active_transcript_lines: list[str] = []

        self._build_ui()
        self._wire_events()
        self._load_initial_settings()
        self._refresh_queue(self._queue_manager.queue_snapshot())

    def _build_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("mainRoot")
        self.setCentralWidget(root)

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(22, 22, 22, 22)
        root_layout.setSpacing(18)

        header_card = QFrame()
        header_card.setObjectName("headerCard")
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(20, 16, 20, 16)
        header_layout.setSpacing(8)

        title_row = QHBoxLayout()
        title_row.setSpacing(12)

        logo_label = QLabel()
        logo_label.setObjectName("appLogo")
        logo_label.setFixedSize(62, 62)
        logo_label.setAlignment(Qt.AlignCenter)
        if not self._brand_icon.isNull():
            logo_label.setPixmap(self._brand_icon.pixmap(56, 56))
        else:
            logo_label.hide()

        title = QLabel("Whisper Watch")
        title.setObjectName("appTitle")
        subtitle = QLabel("Drop media files, queue them up, and stream transcription in real time.")
        subtitle.setObjectName("appSubtitle")
        subtitle.setWordWrap(True)

        title_col = QVBoxLayout()
        title_col.setSpacing(5)
        title_col.addWidget(title)
        title_col.addWidget(subtitle)

        title_row.addWidget(logo_label, 0, Qt.AlignTop)
        title_row.addLayout(title_col, 1)

        header_layout.addLayout(title_row)
        root_layout.addWidget(header_card)

        controls_card = QFrame()
        controls_card.setObjectName("panelCard")
        controls_layout = QHBoxLayout(controls_card)
        controls_layout.setContentsMargins(18, 16, 18, 16)
        controls_layout.setSpacing(12)

        self.output_dir_label = QLabel("Output folder:")
        self.output_dir_label.setObjectName("labelCaption")
        self.output_dir_value = QLabel("")
        self.output_dir_value.setObjectName("valueField")
        self.output_dir_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.output_dir_value.setMinimumWidth(420)

        self.choose_output_button = GlowButton("Choose Folder")
        self.choose_output_button.setObjectName("secondaryButton")

        self.open_output_button = GlowButton("Open Folder")
        self.open_output_button.setObjectName("secondaryButton")

        self.model_label = QLabel("Model:")
        self.model_label.setObjectName("labelCaption")

        self.model_buttons: list[GlowButton] = []
        for label, model_name in self.MODEL_OPTIONS:
            button = GlowButton(label)
            button.setObjectName("modelButton")
            button.setProperty("modelValue", model_name)
            if model_name == DEFAULT_MODEL_NAME:
                button.setProperty("active", True)
            self.model_buttons.append(button)

        controls_layout.addWidget(self.output_dir_label)
        controls_layout.addWidget(self.output_dir_value, 1)
        controls_layout.addWidget(self.choose_output_button)
        controls_layout.addWidget(self.open_output_button)
        controls_layout.addSpacing(8)
        controls_layout.addWidget(self.model_label)
        for button in self.model_buttons:
            controls_layout.addWidget(button)
        root_layout.addWidget(controls_card)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)
        root_layout.addLayout(content_layout, 1)

        left_card = QFrame()
        left_card.setObjectName("panelCard")
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(12)

        drop_title = QLabel("Import")
        drop_title.setObjectName("sectionTitle")
        self.drop_zone = DropZoneWidget()
        self.import_button = GlowButton("Import Files")
        self.import_button.setObjectName("primaryButton")

        queue_title = QLabel("Queue (first in, first out)")
        queue_title.setObjectName("sectionTitle")
        self.queue_list = QListWidget()
        self.queue_list.setObjectName("queueList")

        left_layout.addWidget(drop_title)
        left_layout.addWidget(self.drop_zone)
        left_layout.addWidget(self.import_button)
        left_layout.addSpacing(8)
        left_layout.addWidget(queue_title)
        left_layout.addWidget(self.queue_list, 1)

        content_layout.addWidget(left_card, 1)

        right_card = QFrame()
        right_card.setObjectName("panelCard")
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(12)

        transcript_title = QLabel("Live Transcript")
        transcript_title.setObjectName("sectionTitle")

        self.current_job_label = QLabel("Waiting for files...")
        self.current_job_label.setObjectName("currentJobLabel")

        self.transcript_view = QPlainTextEdit()
        self.transcript_view.setObjectName("transcriptView")
        self.transcript_view.setReadOnly(True)
        self.transcript_view.setPlaceholderText("Whisper output appears here while audio is transcribed.")

        self.status_label = QLabel("Idle")
        self.status_label.setObjectName("statusLabel")
        self.job_progress_bar = QProgressBar()
        self.job_progress_bar.setObjectName("jobProgressBar")
        self.job_progress_bar.setRange(0, 100)
        self.job_progress_bar.setValue(0)
        self.job_progress_bar.setFormat("Idle")

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        self.open_last_srt_button = GlowButton("Open Last SRT")
        self.open_last_srt_button.setObjectName("secondaryButton")
        self.open_last_srt_button.setEnabled(False)

        self.edit_srt_button = GlowButton("Edit SRT in Browser")
        self.edit_srt_button.setObjectName("secondaryButton")

        action_row.addWidget(self.open_last_srt_button)
        action_row.addWidget(self.edit_srt_button)
        action_row.addStretch(1)

        right_layout.addWidget(transcript_title)
        right_layout.addWidget(self.current_job_label)
        right_layout.addWidget(self.transcript_view, 1)
        right_layout.addLayout(action_row)
        right_layout.addWidget(self.job_progress_bar)
        right_layout.addWidget(self.status_label)

        content_layout.addWidget(right_card, 1)

    def _load_brand_icon(self) -> QIcon:
        icon_path = resource_path("assets", "whisperwatch-icon.svg")
        if not icon_path.exists():
            return QIcon()
        return QIcon(str(icon_path))

    def _wire_events(self) -> None:
        self.import_button.clicked.connect(self._import_files)
        self.drop_zone.files_dropped.connect(self._handle_dropped_files)

        self.choose_output_button.clicked.connect(self._choose_output_folder)
        self.open_output_button.clicked.connect(self._open_output_folder)
        self.open_last_srt_button.clicked.connect(self._open_last_srt)
        self.edit_srt_button.clicked.connect(self._open_srt_editor)

        for button in self.model_buttons:
            button.clicked.connect(self._select_model_from_button)

        self._queue_manager.queue_changed.connect(self._refresh_queue)
        self._queue_manager.job_started.connect(self._on_job_started)
        self._queue_manager.job_progress.connect(self._on_job_progress)
        self._queue_manager.segment_received.connect(self._on_segment_received)
        self._queue_manager.job_completed.connect(self._on_job_completed)
        self._queue_manager.job_failed.connect(self._on_job_failed)

    def _load_initial_settings(self) -> None:
        output_dir = self._settings.get_output_dir()
        self.output_dir_value.setText(str(output_dir))

        saved_model = self._settings.get_model_name()
        if saved_model not in [model_value for _, model_value in self.MODEL_OPTIONS]:
            saved_model = DEFAULT_MODEL_NAME
        self._set_active_model_button(saved_model)

    def _current_model_name(self) -> str:
        for button in self.model_buttons:
            if button.property("active") is True:
                return str(button.property("modelValue"))
        return DEFAULT_MODEL_NAME

    def _set_active_model_button(self, model_name: str) -> None:
        for button in self.model_buttons:
            is_active = button.property("modelValue") == model_name
            button.setProperty("active", is_active)
            button.style().unpolish(button)
            button.style().polish(button)
        self._settings.set_model_name(model_name)

    def _select_model_from_button(self) -> None:
        button = self.sender()
        if not isinstance(button, GlowButton):
            return
        model_name = str(button.property("modelValue"))
        self._set_active_model_button(model_name)
        self.status_label.setText(f"Model set to {model_name}.")

    def _import_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select media files",
            "",
            "Media Files (*.*)",
        )
        if files:
            self._enqueue_files(files)

    def _handle_dropped_files(self, file_paths: list[str]) -> None:
        self._enqueue_files(file_paths)

    def _enqueue_files(self, raw_paths: Iterable[str]) -> None:
        file_paths = [Path(path) for path in raw_paths if Path(path).is_file()]
        if not file_paths:
            QMessageBox.warning(self, APP_NAME, "No valid files were added to the queue.")
            return

        output_dir = Path(self.output_dir_value.text())
        model_name = self._current_model_name()

        jobs = self._queue_manager.add_files(file_paths, output_dir, model_name)
        if not jobs:
            QMessageBox.warning(self, APP_NAME, "No files were queued. Please choose valid files.")
            return

        self.status_label.setText(f"Queued {len(jobs)} file(s).")

    def _choose_output_folder(self) -> None:
        selected_folder = QFileDialog.getExistingDirectory(
            self,
            "Choose SRT output folder",
            self.output_dir_value.text(),
        )
        if not selected_folder:
            return

        selected_path = Path(selected_folder).expanduser().resolve()
        selected_path.mkdir(parents=True, exist_ok=True)
        self.output_dir_value.setText(str(selected_path))
        self._settings.set_output_dir(selected_path)
        self.status_label.setText(f"SRT output folder updated: {selected_path}")

    def _open_output_folder(self) -> None:
        output_dir = Path(self.output_dir_value.text())
        output_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(output_dir)))

    def _open_last_srt(self) -> None:
        if self._latest_srt_path is None:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._latest_srt_path)))

    def _open_srt_editor(self) -> None:
        QDesktopServices.openUrl(QUrl(SRT_EDITOR_URL))

    def _refresh_queue(self, jobs: list[TranscriptionJob]) -> None:
        self.queue_list.clear()

        for job in jobs:
            text = f"[{job.status.value}] {job.source_path.name}"
            if job.status == JobStatus.COMPLETED and job.srt_path:
                text += f" -> {job.srt_path.name}"
            if job.status == JobStatus.FAILED and job.error:
                text += f" | {job.error}"

            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, job.job_id)

            if job.status == JobStatus.PROCESSING:
                item.setForeground(QColor("#53E0FF"))
            elif job.status == JobStatus.COMPLETED:
                item.setForeground(QColor("#7BF7B8"))
            elif job.status == JobStatus.FAILED:
                item.setForeground(QColor("#FF7D9E"))
            else:
                item.setForeground(QColor("#D7E4FF"))

            self.queue_list.addItem(item)

    def _on_job_started(self, job: TranscriptionJob) -> None:
        self._active_job_id = job.job_id
        self._active_transcript_lines = []
        self.transcript_view.clear()
        self.current_job_label.setText(f"Now transcribing: {job.source_path.name}")
        self.status_label.setText(f"Processing {job.source_path.name} with {job.model_name}...")
        self.job_progress_bar.setRange(0, 0)
        self.job_progress_bar.setFormat("Starting...")

    def _on_job_progress(self, job_id: str, stage: str, percent: int, detail: str) -> None:
        if job_id != self._active_job_id:
            return

        if percent < 0:
            self.job_progress_bar.setRange(0, 0)
            self.job_progress_bar.setFormat(stage)
        else:
            bounded = max(0, min(100, percent))
            if self.job_progress_bar.minimum() == 0 and self.job_progress_bar.maximum() == 0:
                self.job_progress_bar.setRange(0, 100)
            self.job_progress_bar.setValue(bounded)
            self.job_progress_bar.setFormat(f"{bounded}%")

        if detail:
            self.status_label.setText(f"{stage} | {detail}")
        else:
            self.status_label.setText(stage)

    def _on_segment_received(self, job_id: str, start: float, _end: float, text: str) -> None:
        if job_id != self._active_job_id:
            return
        self._active_transcript_lines.append(text)
        self.transcript_view.appendPlainText(f"[{timestamp_for_log(start)}] {text}")

    def _on_job_completed(self, job: TranscriptionJob) -> None:
        if job.job_id == self._active_job_id:
            self._active_job_id = None

        self._latest_srt_path = job.srt_path
        self.open_last_srt_button.setEnabled(self._latest_srt_path is not None)

        self.current_job_label.setText(f"Completed: {job.source_path.name}")
        self.job_progress_bar.setRange(0, 100)
        self.job_progress_bar.setValue(100)
        self.job_progress_bar.setFormat("100%")
        if job.srt_path:
            self.status_label.setText(f"SRT saved to {job.srt_path}")
        else:
            self.status_label.setText(f"Completed {job.source_path.name}.")

    def _on_job_failed(self, job: TranscriptionJob) -> None:
        if job.job_id == self._active_job_id:
            self._active_job_id = None
        self.current_job_label.setText(f"Failed: {job.source_path.name}")
        self.job_progress_bar.setRange(0, 100)
        self.job_progress_bar.setValue(0)
        self.job_progress_bar.setFormat("Failed")
        self.status_label.setText(job.error or "Transcription failed.")
