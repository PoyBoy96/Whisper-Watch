from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Sequence

from PySide6.QtCore import QObject, QThread, Signal

from app.core.srt_service import SrtService
from app.core.transcription_models import JobStatus, TranscriptionJob
from app.core.transcription_worker import TranscriptionWorker
from app.core.whisper_service import WhisperService


class TranscriptionQueueManager(QObject):
    queue_changed = Signal(object)
    job_started = Signal(object)
    job_progress = Signal(str, str, int, str)
    segment_received = Signal(str, float, float, str)
    job_completed = Signal(object)
    job_failed = Signal(object)

    def __init__(
        self,
        whisper_service: WhisperService,
        srt_service: SrtService,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._whisper_service = whisper_service
        self._srt_service = srt_service
        self._jobs: dict[str, TranscriptionJob] = {}
        self._job_order: list[str] = []
        self._queued_job_ids: deque[str] = deque()

        self._active_job_id: str | None = None
        self._active_thread: QThread | None = None
        self._active_worker: TranscriptionWorker | None = None

    def add_files(self, file_paths: Sequence[Path], output_dir: Path, model_name: str) -> list[TranscriptionJob]:
        resolved_output = output_dir.expanduser().resolve()
        resolved_output.mkdir(parents=True, exist_ok=True)

        new_jobs: list[TranscriptionJob] = []
        for file_path in file_paths:
            path = file_path.expanduser()
            if not path.is_file():
                continue

            job = TranscriptionJob(
                source_path=path.resolve(),
                output_dir=resolved_output,
                model_name=model_name,
            )

            self._jobs[job.job_id] = job
            self._job_order.append(job.job_id)
            self._queued_job_ids.append(job.job_id)
            new_jobs.append(job)

        if new_jobs:
            self._emit_queue_snapshot()
            self._try_start_next_job()

        return new_jobs

    def queue_snapshot(self) -> list[TranscriptionJob]:
        return [self._jobs[job_id] for job_id in self._job_order]

    def _emit_queue_snapshot(self) -> None:
        self.queue_changed.emit(self.queue_snapshot())

    def _try_start_next_job(self) -> None:
        if self._active_thread is not None:
            return
        if not self._queued_job_ids:
            return

        job_id = self._queued_job_ids.popleft()
        job = self._jobs[job_id]

        job.status = JobStatus.PROCESSING
        self._active_job_id = job_id
        self._emit_queue_snapshot()
        self.job_started.emit(job)

        self._active_worker = TranscriptionWorker(job, self._whisper_service, self._srt_service)
        self._active_thread = QThread(self)
        self._active_worker.moveToThread(self._active_thread)

        self._active_thread.started.connect(self._active_worker.run)
        self._active_worker.progress.connect(self.job_progress)
        self._active_worker.segment_ready.connect(self.segment_received)
        self._active_worker.finished.connect(self._on_worker_finished)
        self._active_worker.failed.connect(self._on_worker_failed)
        self._active_worker.finished.connect(self._active_thread.quit)
        self._active_worker.failed.connect(self._active_thread.quit)
        self._active_thread.finished.connect(self._active_worker.deleteLater)
        self._active_thread.finished.connect(self._active_thread.deleteLater)
        self._active_thread.finished.connect(self._on_thread_finished)

        self._active_thread.start()

    def _on_worker_finished(self, job_id: str, transcript: str, srt_path: str) -> None:
        job = self._jobs[job_id]
        job.status = JobStatus.COMPLETED
        job.transcript = transcript
        job.srt_path = Path(srt_path)
        job.error = None

        self._active_job_id = None
        self.job_completed.emit(job)
        self._emit_queue_snapshot()

    def _on_worker_failed(self, job_id: str, error: str) -> None:
        job = self._jobs[job_id]
        job.status = JobStatus.FAILED
        job.error = error

        self._active_job_id = None
        self.job_failed.emit(job)
        self._emit_queue_snapshot()

    def _on_thread_finished(self) -> None:
        self._active_thread = None
        self._active_worker = None
        self._try_start_next_job()
