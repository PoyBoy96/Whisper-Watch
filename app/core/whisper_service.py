from __future__ import annotations

import os
import time
from pathlib import Path, PurePosixPath
from threading import Lock
from typing import Callable, Iterator

import huggingface_hub
import requests
from faster_whisper import WhisperModel
from faster_whisper.utils import _MODELS as FASTER_WHISPER_MODELS
from tqdm.auto import tqdm

from app.core.transcription_models import TranscriptSegment

ProgressCallback = Callable[[str, int, str], None]


def _format_eta(seconds: float | None) -> str:
    if seconds is None:
        return "estimating..."
    remaining = max(0, int(seconds))
    hours, remainder = divmod(remaining, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours:d}h {minutes:02}m {secs:02}s"
    if minutes > 0:
        return f"{minutes:d}m {secs:02}s"
    return f"{secs:d}s"


class _DownloadProgressTracker:
    def __init__(
        self,
        total_bytes: int,
        completed_bytes: int,
        callback: ProgressCallback | None,
    ) -> None:
        self.total_bytes = max(1, total_bytes)
        self.completed_bytes = max(0, min(completed_bytes, self.total_bytes))
        self.callback = callback
        self.stage = "Downloading model"

        self._started_at = time.monotonic()
        self._last_emit = 0.0
        self._last_percent = -1

    def set_stage(self, stage: str) -> None:
        self.stage = stage
        self.emit(force=True)

    def add_bytes(self, byte_count: float) -> None:
        if byte_count <= 0:
            return
        self.completed_bytes = min(self.total_bytes, self.completed_bytes + int(byte_count))
        self.emit(force=False)

    def emit(self, force: bool) -> None:
        if self.callback is None:
            return

        percent = int(round((self.completed_bytes / self.total_bytes) * 100))
        now = time.monotonic()

        if not force and percent == self._last_percent and (now - self._last_emit) < 0.2:
            return

        elapsed = max(0.001, now - self._started_at)
        remaining_bytes = max(0, self.total_bytes - self.completed_bytes)
        eta_seconds = None
        if self.completed_bytes > 0 and remaining_bytes > 0:
            rate = self.completed_bytes / elapsed
            if rate > 0:
                eta_seconds = remaining_bytes / rate

        detail = f"ETA {_format_eta(eta_seconds)}"
        self.callback(self.stage, percent, detail)

        self._last_percent = percent
        self._last_emit = now

    def build_tqdm_class(self) -> type[tqdm]:
        tracker = self

        class CallbackTqdm(tqdm):
            def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
                # huggingface_hub can pass a "name" kwarg that some tqdm
                # variants reject with "Unknown argument(s)".
                kwargs.pop("name", None)
                # Windowed app builds may not have an attached stderr/stdout.
                # Disable terminal rendering but keep update callbacks active.
                kwargs["disable"] = True
                self._track_bytes = kwargs.get("unit") in {"B", "iB"} or bool(kwargs.get("unit_scale"))
                self._last_n = 0.0
                super().__init__(*args, **kwargs)

            def update(self, n=1) -> None:  # noqa: ANN001
                super().update(n)
                if not self._track_bytes:
                    return
                delta = float(self.n - self._last_n)
                if delta > 0:
                    self._last_n = float(self.n)
                    tracker.add_bytes(delta)

            def close(self) -> None:
                if self._track_bytes:
                    delta = float(self.n - self._last_n)
                    if delta > 0:
                        self._last_n = float(self.n)
                        tracker.add_bytes(delta)
                super().close()

        return CallbackTqdm


class _SilentTqdm(tqdm):
    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        kwargs.pop("name", None)
        kwargs["disable"] = True
        super().__init__(*args, **kwargs)


class WhisperService:
    GPU_ENV_FLAG = "WHISPER_WATCH_USE_GPU"
    ALLOW_PATTERNS = [
        "config.json",
        "preprocessor_config.json",
        "model.bin",
        "tokenizer.json",
        "vocabulary.*",
    ]

    def __init__(self) -> None:
        self._model_name: str | None = None
        self._model: WhisperModel | None = None
        self._model_source: str | None = None
        self._device: str | None = None
        self._lock = Lock()

    @staticmethod
    def _looks_like_cuda_runtime_error(error: Exception) -> bool:
        message = str(error).lower()
        markers = (
            "cublas64",
            "cublas",
            "cudnn",
            "cuda",
            "failed to load",
            "cannot be loaded",
        )
        return any(marker in message for marker in markers)

    @classmethod
    def _gpu_enabled(cls) -> bool:
        return os.environ.get(cls.GPU_ENV_FLAG, "0").strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _resolve_repo_id(model_name: str) -> str:
        if "/" in model_name:
            return model_name
        repo_id = FASTER_WHISPER_MODELS.get(model_name)
        if repo_id is None:
            raise ValueError(f"Unknown Whisper model: {model_name}")
        return repo_id

    def _build_cpu_model(self, model_source: str) -> WhisperModel:
        self._device = "cpu"
        return WhisperModel(model_source, device="cpu", compute_type="int8")

    def _try_load_local_snapshot(self, repo_id: str) -> str:
        return huggingface_hub.snapshot_download(
            repo_id=repo_id,
            allow_patterns=self.ALLOW_PATTERNS,
            local_files_only=True,
            tqdm_class=_SilentTqdm,
        )

    def _split_remote_filename(self, remote_filename: str) -> tuple[str, str | None]:
        path = PurePosixPath(remote_filename)
        subfolder = str(path.parent) if str(path.parent) != "." else None
        return path.name, subfolder

    def _ensure_model_available(self, model_name: str, progress_callback: ProgressCallback | None) -> str:
        repo_id = self._resolve_repo_id(model_name)

        if progress_callback is not None:
            progress_callback("Checking model cache", -1, "Looking for existing local files...")

        try:
            dry_run_infos = huggingface_hub.snapshot_download(
                repo_id=repo_id,
                allow_patterns=self.ALLOW_PATTERNS,
                dry_run=True,
                local_files_only=False,
                tqdm_class=_SilentTqdm,
            )
        except (huggingface_hub.utils.HfHubHTTPError, requests.exceptions.RequestException):
            if progress_callback is not None:
                progress_callback("Network unavailable", -1, "Trying local cache only...")
            try:
                model_path = self._try_load_local_snapshot(repo_id)
                if progress_callback is not None:
                    progress_callback("Model ready", 100, "Using local cache.")
                return model_path
            except Exception as cache_error:  # noqa: BLE001
                raise RuntimeError(
                    "Unable to download Whisper model and no local cache was found."
                ) from cache_error

        if isinstance(dry_run_infos, str):
            dry_run_infos = []

        total_bytes = sum(int(file_info.file_size) for file_info in dry_run_infos)
        cached_bytes = sum(
            int(file_info.file_size) for file_info in dry_run_infos if not file_info.will_download
        )
        files_to_download = [file_info for file_info in dry_run_infos if file_info.will_download]

        if total_bytes > 0:
            tracker = _DownloadProgressTracker(total_bytes, cached_bytes, progress_callback)
            if not files_to_download:
                tracker.stage = "Model ready"
                tracker.completed_bytes = tracker.total_bytes
                tracker.emit(force=True)
                if progress_callback is not None:
                    progress_callback("Model ready", 100, "Already installed in local cache.")
            else:
                total_files = len(files_to_download)
                tracker.emit(force=True)
                for index, file_info in enumerate(files_to_download, start=1):
                    tracker.set_stage(f"Downloading model ({index}/{total_files})")
                    filename, subfolder = self._split_remote_filename(file_info.filename)
                    try:
                        huggingface_hub.hf_hub_download(
                            repo_id=repo_id,
                            filename=filename,
                            subfolder=subfolder,
                            local_files_only=False,
                            force_download=False,
                            tqdm_class=tracker.build_tqdm_class(),
                        )
                    except Exception as progress_error:  # noqa: BLE001
                        # Progress hooks should never break transcription.
                        if "Unknown argument(s)" not in str(progress_error):
                            raise
                        huggingface_hub.hf_hub_download(
                            repo_id=repo_id,
                            filename=filename,
                            subfolder=subfolder,
                            local_files_only=False,
                            force_download=False,
                            tqdm_class=_SilentTqdm,
                        )
                        tracker.add_bytes(file_info.file_size)

                tracker.stage = "Finalizing model"
                tracker.completed_bytes = tracker.total_bytes
                tracker.emit(force=True)
        elif progress_callback is not None:
            progress_callback("Model ready", 100, "Model files are already available.")

        return self._try_load_local_snapshot(repo_id)

    def _get_model(
        self,
        model_name: str,
        progress_callback: ProgressCallback | None = None,
    ) -> WhisperModel:
        with self._lock:
            if self._model is not None and self._model_name == model_name:
                if progress_callback is not None:
                    progress_callback("Model ready", 100, "Using in-memory model.")
                return self._model

            model_source = self._ensure_model_available(model_name, progress_callback)
            if progress_callback is not None:
                progress_callback("Loading model", -1, "Initializing Whisper runtime...")

            # Default to CPU for maximum compatibility. GPU can be enabled with
            # WHISPER_WATCH_USE_GPU=1.
            if not self._gpu_enabled():
                self._model = self._build_cpu_model(model_source)
            else:
                # Prefer auto device selection. If CUDA runtime libraries are missing,
                # transparently fall back to CPU mode.
                try:
                    self._model = WhisperModel(model_source, device="auto", compute_type="default")
                    self._device = "auto"
                except Exception as exc:  # noqa: BLE001
                    if not self._looks_like_cuda_runtime_error(exc):
                        raise
                    if progress_callback is not None:
                        progress_callback("GPU unavailable", -1, "Switching to CPU mode...")
                    self._model = self._build_cpu_model(model_source)

            self._model_name = model_name
            self._model_source = model_source
            if progress_callback is not None:
                progress_callback("Model loaded", 100, f"Device: {self._device}")
            return self._model

    def stream_transcription(
        self,
        media_path: Path,
        model_name: str,
        progress_callback: ProgressCallback | None = None,
    ) -> Iterator[TranscriptSegment]:
        model = self._get_model(model_name, progress_callback=progress_callback)

        if progress_callback is not None:
            progress_callback("Transcribing audio", -1, "Running inference...")

        try:
            segments, _ = model.transcribe(
                str(media_path),
                task="transcribe",
                beam_size=5,
                vad_filter=True,
                word_timestamps=False,
            )
        except Exception as exc:  # noqa: BLE001
            # If GPU mode was enabled and runtime fails at first transcription call,
            # rebuild the model on CPU and retry once.
            if not self._looks_like_cuda_runtime_error(exc):
                raise

            with self._lock:
                if progress_callback is not None:
                    progress_callback("GPU unavailable", -1, "Retrying on CPU...")
                source = self._model_source or model_name
                self._model = self._build_cpu_model(source)
                self._model_name = model_name
                self._model_source = source
                model = self._model

            segments, _ = model.transcribe(
                str(media_path),
                task="transcribe",
                beam_size=5,
                vad_filter=True,
                word_timestamps=False,
            )

        if progress_callback is not None:
            progress_callback("Streaming transcript", -1, "Receiving recognized segments...")

        for segment in segments:
            text = segment.text.strip()
            if not text:
                continue
            yield TranscriptSegment(start=float(segment.start), end=float(segment.end), text=text)
