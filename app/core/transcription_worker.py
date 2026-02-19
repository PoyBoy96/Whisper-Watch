from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from app.core.srt_service import SrtService
from app.core.transcription_models import TranscriptionJob, TranscriptSegment
from app.core.whisper_service import WhisperService


class TranscriptionWorker(QObject):
    segment_ready = Signal(str, float, float, str)
    progress = Signal(str, str, int, str)
    finished = Signal(str, str, str)
    failed = Signal(str, str)

    def __init__(
        self,
        job: TranscriptionJob,
        whisper_service: WhisperService,
        srt_service: SrtService,
    ) -> None:
        super().__init__()
        self._job = job
        self._whisper_service = whisper_service
        self._srt_service = srt_service

    @Slot()
    def run(self) -> None:
        try:
            self.progress.emit(self._job.job_id, "Starting job", -1, "Preparing transcription worker...")
            segments: list[TranscriptSegment] = []
            transcript_lines: list[str] = []

            for segment in self._whisper_service.stream_transcription(
                self._job.source_path,
                self._job.model_name,
                progress_callback=self._on_progress_update,
            ):
                segments.append(segment)
                transcript_lines.append(segment.text)
                self.segment_ready.emit(self._job.job_id, segment.start, segment.end, segment.text)

            transcript = "\n".join(transcript_lines).strip()
            self.progress.emit(self._job.job_id, "Writing subtitles", -1, "Saving SRT file...")
            srt_path = self._srt_service.write_srt(
                segments=segments,
                source_media_path=self._job.source_path,
                output_dir=self._job.output_dir,
            )

            self.progress.emit(self._job.job_id, "Complete", 100, "Transcription finished.")
            self.finished.emit(self._job.job_id, transcript, str(srt_path))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(self._job.job_id, str(exc))

    def _on_progress_update(self, stage: str, percent: int, detail: str) -> None:
        self.progress.emit(self._job.job_id, stage, percent, detail)
