from __future__ import annotations

import os
import re
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests
from PySide6.QtCore import QObject, Signal

from app.config import APP_REPO_URL, UPDATER_USER_AGENT


@dataclass(slots=True, frozen=True)
class UpdateRelease:
    tag_name: str
    html_url: str
    body: str
    asset_name: str
    asset_download_url: str
    asset_size: int | None


def _parse_version(value: str) -> tuple[int, ...]:
    cleaned = value.strip()
    if cleaned.lower().startswith("v"):
        cleaned = cleaned[1:]
    return tuple(int(match) for match in re.findall(r"\d+", cleaned))


def _is_newer_version(remote: str, local: str) -> bool:
    remote_parts = _parse_version(remote)
    local_parts = _parse_version(local)
    if not remote_parts or not local_parts:
        return False

    width = max(len(remote_parts), len(local_parts))
    remote_padded = remote_parts + (0,) * (width - len(remote_parts))
    local_padded = local_parts + (0,) * (width - len(local_parts))
    return remote_padded > local_padded


def _repo_slug_from_url(repo_url: str) -> str:
    parsed = urlparse(repo_url)
    path = parsed.path or repo_url
    path = path.strip().strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    parts = [part for part in path.split("/") if part]
    if len(parts) < 2:
        return ""
    return f"{parts[0]}/{parts[1]}"


def _format_bytes(byte_count: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(byte_count)
    unit = units[0]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            break
        value /= 1024
    if unit == "B":
        return f"{int(value)} {unit}"
    return f"{value:.1f} {unit}"


def _format_eta(seconds_remaining: float) -> str:
    remaining = max(int(seconds_remaining), 0)
    minutes, seconds = divmod(remaining, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02}:{minutes:02}:{seconds:02}"
    return f"{minutes:02}:{seconds:02}"


class UpdateService(QObject):
    check_started = Signal()
    check_completed = Signal(object, str)

    install_status = Signal(str)
    install_progress = Signal(int, str)
    install_ready = Signal()
    install_failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._check_in_progress = False
        self._install_in_progress = False

    def check_for_update_async(self, current_version: str) -> None:
        if self._check_in_progress:
            return
        self._check_in_progress = True
        self.check_started.emit()

        thread = threading.Thread(
            target=self._check_worker,
            args=(current_version,),
            daemon=True,
        )
        thread.start()

    def install_update_async(
        self,
        release: UpdateRelease,
        current_exe: Path,
        install_dir: Path,
    ) -> None:
        if self._install_in_progress:
            return
        self._install_in_progress = True

        thread = threading.Thread(
            target=self._install_worker,
            args=(release, current_exe, install_dir),
            daemon=True,
        )
        thread.start()

    def _check_worker(self, current_version: str) -> None:
        try:
            repo_slug = _repo_slug_from_url(APP_REPO_URL)
            if not repo_slug:
                self.check_completed.emit(None, "Update repository URL is invalid.")
                return

            release = self._fetch_latest_release(repo_slug)
            if release and _is_newer_version(release.tag_name, current_version):
                self.check_completed.emit(release, "")
                return

            self.check_completed.emit(None, "")
        except Exception as exc:
            self.check_completed.emit(None, f"Update check failed: {exc}")
        finally:
            self._check_in_progress = False

    def _fetch_latest_release(self, repo_slug: str) -> UpdateRelease | None:
        api_url = f"https://api.github.com/repos/{repo_slug}/releases/latest"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": UPDATER_USER_AGENT,
        }
        response = requests.get(api_url, headers=headers, timeout=12)
        if response.status_code == 404:
            return None
        response.raise_for_status()

        payload = response.json()
        tag_name = str(payload.get("tag_name") or "").strip()
        if not tag_name:
            return None

        assets = payload.get("assets") or []
        exe_assets = [asset for asset in assets if str(asset.get("name", "")).lower().endswith(".exe")]
        if not exe_assets:
            return None

        preferred_asset = next(
            (
                asset
                for asset in exe_assets
                if "installer" in str(asset.get("name", "")).lower()
                or "setup" in str(asset.get("name", "")).lower()
            ),
            exe_assets[0],
        )
        download_url = str(preferred_asset.get("browser_download_url") or "").strip()
        if not download_url:
            return None

        return UpdateRelease(
            tag_name=tag_name,
            html_url=str(payload.get("html_url") or ""),
            body=str(payload.get("body") or ""),
            asset_name=str(preferred_asset.get("name") or "WhisperWatchInstaller.exe"),
            asset_download_url=download_url,
            asset_size=preferred_asset.get("size"),
        )

    def _install_worker(self, release: UpdateRelease, current_exe: Path, install_dir: Path) -> None:
        try:
            self.install_status.emit("Downloading update package...")
            temp_root = Path(tempfile.gettempdir()) / "WhisperWatchUpdater"
            temp_root.mkdir(parents=True, exist_ok=True)

            safe_asset_name = release.asset_name if release.asset_name.lower().endswith(".exe") else "WhisperWatchInstaller.exe"
            installer_path = temp_root / safe_asset_name
            if installer_path.exists():
                installer_path.unlink()

            start_time = time.monotonic()
            headers = {
                "Accept": "application/octet-stream",
                "User-Agent": UPDATER_USER_AGENT,
            }
            with requests.get(release.asset_download_url, headers=headers, stream=True, timeout=30) as response:
                response.raise_for_status()
                total = response.headers.get("Content-Length")
                total_bytes = int(total) if total and total.isdigit() else release.asset_size
                downloaded = 0
                chunk_size = 1024 * 256

                with open(installer_path, "wb") as output_file:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if not chunk:
                            continue
                        output_file.write(chunk)
                        downloaded += len(chunk)

                        elapsed = max(time.monotonic() - start_time, 0.001)
                        speed = downloaded / elapsed
                        eta_text = ""

                        if total_bytes and total_bytes > 0:
                            remaining = max(total_bytes - downloaded, 0)
                            eta_seconds = remaining / speed if speed > 0 else 0
                            eta_text = f" | ETA {_format_eta(eta_seconds)}"
                            percent = int((downloaded / total_bytes) * 100)
                            bounded_percent = max(0, min(100, percent))
                            detail = (
                                f"{_format_bytes(downloaded)} / {_format_bytes(total_bytes)}"
                                f" @ {_format_bytes(int(speed))}/s{eta_text}"
                            )
                            self.install_progress.emit(bounded_percent, detail)
                        else:
                            detail = f"{_format_bytes(downloaded)} downloaded"
                            self.install_progress.emit(-1, detail)

            self.install_status.emit("Preparing installer...")
            updater_script_path = temp_root / "apply_update.cmd"
            updater_log_path = temp_root / "update_log.txt"

            updater_script = self._build_updater_script(
                process_id=os.getpid(),
                installer_path=installer_path,
                install_dir=install_dir,
                executable_name=current_exe.name,
                log_path=updater_log_path,
            )
            updater_script_path.write_text(updater_script, encoding="utf-8")

            creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            subprocess.Popen(
                ["cmd", "/c", str(updater_script_path)],
                creationflags=creation_flags,
            )

            self.install_status.emit("Installer launched. Restarting app...")
            self.install_ready.emit()
        except Exception as exc:
            self.install_failed.emit(f"Update install failed: {exc}")
            self._install_in_progress = False

    def _build_updater_script(
        self,
        process_id: int,
        installer_path: Path,
        install_dir: Path,
        executable_name: str,
        log_path: Path,
    ) -> str:
        lines = [
            "@echo off",
            "setlocal",
            f"set \"LOG={log_path}\"",
            f"set \"PID={process_id}\"",
            f"set \"INSTALLER={installer_path}\"",
            f"set \"TARGET_DIR={install_dir}\"",
            f"set \"TARGET_EXE={executable_name}\"",
            "echo [%date% %time%] Whisper Watch updater started > \"%LOG%\"",
            ":wait_for_app_exit",
            "tasklist /FI \"PID eq %PID%\" | find /I \"%PID%\" >nul",
            "if not errorlevel 1 (",
            "  timeout /t 1 /nobreak >nul",
            "  goto wait_for_app_exit",
            ")",
            "echo [%date% %time%] Running installer... >> \"%LOG%\"",
            "\"%INSTALLER%\" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /CLOSEAPPLICATIONS /DIR=\"%TARGET_DIR%\" >> \"%LOG%\" 2>&1",
            "set \"RC=%ERRORLEVEL%\"",
            "echo [%date% %time%] Installer exit code: %RC% >> \"%LOG%\"",
            "if not \"%RC%\"==\"0\" goto cleanup",
            "timeout /t 1 /nobreak >nul",
            "start \"\" \"%TARGET_DIR%\\%TARGET_EXE%\"",
            ":cleanup",
            "del /f /q \"%INSTALLER%\" >nul 2>&1",
            "del /f /q \"%~f0\" >nul 2>&1",
            "endlocal",
        ]
        return "\r\n".join(lines) + "\r\n"
