from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

from app.core.transcription_models import TranscriptSegment


def to_srt_timestamp(seconds: float) -> str:
    milliseconds_total = int(max(0.0, seconds) * 1000)
    hours, remainder = divmod(milliseconds_total, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1_000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


class SrtService:
    def write_srt(
        self,
        segments: Iterable[TranscriptSegment],
        source_media_path: Path,
        output_dir: Path,
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)

        base_name = source_media_path.stem
        srt_path = output_dir / f"{base_name}.srt"
        if srt_path.exists():
            suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
            srt_path = output_dir / f"{base_name}_{suffix}.srt"

        segment_list = list(segments)
        with srt_path.open("w", encoding="utf-8") as handle:
            for index, segment in enumerate(segment_list, start=1):
                handle.write(f"{index}\n")
                handle.write(f"{to_srt_timestamp(segment.start)} --> {to_srt_timestamp(segment.end)}\n")
                handle.write(f"{segment.text}\n\n")

        return srt_path

