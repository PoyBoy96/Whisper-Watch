# Whisper Watch

Desktop transcription app with a modern tech-style UI, drag-and-drop import, FIFO queueing, and local Whisper transcription.

## Features

- Accepts audio/video files (mp3, wav, mp4, and most formats supported by local FFmpeg/PyAV decoding).
- Uses local `faster-whisper` models with default set to `large-v3`.
- Real-time transcript stream while each file is being processed.
- Model install/load progress with status and ETA feedback (avoids "frozen" first-run experience).
- Queue system (first in, first out) so only one file transcribes at a time.
- Auto-generates and saves `.srt` for every job.
- Defaults SRT output to `~/Downloads/WhisperWatch` with folder picker override.
- Built-in link button for SRT editing (`https://matthewpenkala.com/srt-editor`).
- In-app update notification bell (red badge when a newer GitHub Release is available).
- One-click in-place auto-update from the latest installer release asset.
- Centralized styling in one file: `app/ui/styles.qss`.

## Workspace Layout

- `app/main.py`: app entrypoint
- `app/config.py`: constants and resource lookup
- `app/core/transcription_models.py`: job + segment data models
- `app/core/settings_store.py`: persisted app settings
- `app/core/whisper_service.py`: Whisper model loading + streaming transcription
- `app/core/srt_service.py`: SRT formatting + file writing
- `app/core/transcription_worker.py`: background worker for one job
- `app/core/queue_manager.py`: FIFO queue orchestration (single active worker)
- `app/core/update_service.py`: GitHub release check + download + in-place installer handoff
- `app/version.py`: app version used for update comparisons
- `app/ui/widgets.py`: reusable UI widgets (glow buttons + drag/drop zone)
- `app/ui/main_window.py`: main UI layout + signal wiring
- `app/ui/styles.qss`: global styles
- `scripts/run_dev.ps1`: run in dev mode
- `scripts/build_exe.ps1`: build standalone app folder with PyInstaller
- `scripts/build_installer.ps1`: build installer `.exe` using Inno Setup
- `installer/WhisperWatch.iss`: Inno Setup installer config

## Run (Development)

```powershell
.\scripts\run_dev.ps1
```

## Build Executable

```powershell
.\scripts\build_exe.ps1
```

Result: `dist\WhisperWatch\WhisperWatch.exe`

## Build Installer EXE

1. Install Inno Setup 6.
2. Run:

```powershell
.\scripts\build_installer.ps1
```

Result: `dist-installer\WhisperWatchInstaller_v1_0_1.exe`

## Auto-Update Requirements

- Publish GitHub Releases in `PoyBoy96/Whisper-Watch`.
- Tag each release with a semantic version like `v1.0.1`.
- Attach the installer `.exe` asset to each release.
- The app checks releases at launch and compares release tag vs `app/version.py`.

## Notes

- First use of a Whisper model downloads model files locally (one-time).
- `large-v3` is accurate but heavy; make sure the target machine has enough RAM and disk.
- GPU is disabled by default for compatibility. To opt into GPU auto-detection, set `WHISPER_WATCH_USE_GPU=1` before launching.
- SRT output is standard SubRip format (`index`, `start --> end`, `text`).
- Branded icon source is `assets/whisperwatch-icon.svg`. If you add `assets/whisperwatch-icon.ico`, build scripts will use it for the Windows executable icon.
