"""SoAI - Protected POSIX installation command and probe evidence [backend/core/bootstrap/install_diagnostics.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import re
import shlex
import signal
import stat
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from types import FrameType

from core.errors.exceptions import StateError
from core.system.commands import CommandResult
from core.system.process_launcher import spawn_managed_process

__all__ = (
    "InstallDiagnostics",
    "read_install_diagnostics_context",
    "configure_install_cancellation",
)


@dataclass(frozen=True, slots=True)
class InstallDiagnostics:
    directory: str

    def record_probe(self, label: str, result: CommandResult, *, terminal: bool = False) -> None:
        attempt = tempfile.mkdtemp(prefix="probe.", dir=self.directory)
        self._write(os.path.join(attempt, "stdout.log"), result.stdout)
        self._write(os.path.join(attempt, "stderr.log"), result.stderr)
        self._record_attempt(attempt, label, result.return_code, terminal=terminal)

    def record_warning(self, message: str) -> None:
        descriptor, path = tempfile.mkstemp(prefix="warning.", dir=self.directory)
        os.close(descriptor)
        self._write(path, message)

    def run(
        self,
        command: list[str],
        *,
        label: str,
        cwd: str | None,
        env: Mapping[str, str] | None,
    ) -> None:
        attempt = tempfile.mkdtemp(prefix="command.", dir=self.directory)
        stdout_path = os.path.join(attempt, "stdout.log")
        stderr_path = os.path.join(attempt, "stderr.log")
        stdout_fd = os.open(stdout_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            stderr_fd = os.open(stderr_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with spawn_managed_process(
                    command,
                    cwd=cwd,
                    env=env,
                    stdout=stdout_fd,
                    stderr=stderr_fd,
                    start_new_session=True,
                ) as process:
                    try:
                        return_code = process.wait()
                    except KeyboardInterrupt:
                        os.killpg(process.pid, signal.SIGTERM)
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            os.killpg(process.pid, signal.SIGKILL)
                            process.wait()
                        self._record_attempt(attempt, label, 130, terminal=False)
                        raise
            finally:
                os.close(stderr_fd)
        finally:
            os.close(stdout_fd)
        identity = f"{label}: {shlex.join(command)}"
        self._record_attempt(attempt, identity, return_code, terminal=True)
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, command)

    def _record_attempt(self, attempt: str, label: str, code: int, *, terminal: bool) -> None:
        for name in ("stdout.log", "stderr.log"):
            path = os.path.join(attempt, name)
            with open(path, encoding="utf-8", errors="replace") as stream:
                content = stream.read()
            self._write(path, content)
        self._write(os.path.join(attempt, "check.txt"), f"{label}\n")
        self._write(os.path.join(attempt, "exit-code.txt"), f"{code}\n")
        with open(os.path.join(attempt, "stdout.log"), encoding="utf-8", errors="strict") as stream:
            stdout = stream.read()
        with open(os.path.join(attempt, "stderr.log"), encoding="utf-8", errors="strict") as stream:
            stderr = stream.read()
        log_fd = os.open(
            os.path.join(self.directory, "install.log"),
            os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW,
        )
        with os.fdopen(log_fd, "a", encoding="utf-8") as log:
            log.write(
                _safe_text(
                    f"\nTime: {datetime.now(UTC).isoformat()}\nCheck: {label}\nExit code: {code}\n{stdout}{stderr}"
                )
            )
        failure_path = os.path.join(self.directory, "failure.txt")
        if code != 0 and terminal and not os.path.exists(failure_path):
            self._write(failure_path, f"{label}\n{code}\n")
            self._write(os.path.join(self.directory, "excerpt.log"), stdout + stderr)

    def _write(self, path: str, text: str) -> None:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", errors="strict") as stream:
            stream.write(_safe_text(text))


def read_install_diagnostics_context() -> InstallDiagnostics | None:
    if os.name != "posix" or os.environ.get("SOAI_INSTALL_UI_CONTEXT", "") != "1":
        return None
    directory = os.environ.get("SOAI_INSTALL_DIAGNOSTICS_DIR", "")
    if not directory or not os.path.isabs(directory) or os.path.normpath(directory) != directory:
        raise StateError("The installer diagnostic directory is invalid.")
    parent_metadata = os.stat(os.path.dirname(directory))
    parent_mode = stat.S_IMODE(parent_metadata.st_mode)
    parent_is_writable_by_others = parent_mode & 0o022 != 0
    parent_has_sticky_bit = parent_mode & stat.S_ISVTX != 0
    if parent_metadata.st_uid != 0 or (parent_is_writable_by_others and not parent_has_sticky_bit):
        raise StateError("The installer diagnostic directory is invalid.")
    metadata = os.lstat(directory)
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) != 0o700
        or not os.path.basename(directory).startswith("soai-install.")
    ):
        raise StateError("The installer diagnostic directory has unsafe ownership or permissions.")
    log_path = os.path.join(directory, "install.log")
    log_metadata = os.lstat(log_path)
    if (
        not stat.S_ISREG(log_metadata.st_mode)
        or log_metadata.st_uid != os.geteuid()
        or stat.S_IMODE(log_metadata.st_mode) != 0o600
    ):
        raise StateError("The installer diagnostic log has unsafe ownership or permissions.")
    return InstallDiagnostics(directory)


def _safe_text(text: str) -> str:
    value = re.sub(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)", "", text)
    value = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", value)
    value = re.sub(r"(https?://)[^/@\s]+@", r"\1[REDACTED]@", value)
    value = re.sub(r"(authorization:\s*)[^\n]*", r"\1[REDACTED]", value, flags=re.IGNORECASE)
    value = re.sub(
        r"([?&](?:token|key|api_key|password|secret)=)[^&\s]+",
        r"\1[REDACTED]",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"((?:token|password|secret|api_key)\s*[:=]\s*)[^\s]+",
        r"\1[REDACTED]",
        value,
        flags=re.IGNORECASE,
    )
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value).replace("\r", "\n")


def _install_cancellation_handler(_signal_number: int, _frame: FrameType | None) -> None:
    raise KeyboardInterrupt


def configure_install_cancellation(diagnostics: InstallDiagnostics | None) -> None:
    if diagnostics is not None:
        signal.signal(signal.SIGTERM, _install_cancellation_handler)
