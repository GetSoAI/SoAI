"""SoAI - Job and response file I/O for IPC [backend/core/ipc/job_files.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.filesystem.atomic_writes import atomic_write_text_content
from core.filesystem.open_files import open_text
from core.hardware.reservation_claims import claim_reserved_write
from core.logging.trace import get_logger
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_value
from core.timing.epoch import epoch_seconds_float

if TYPE_CHECKING:
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.types.json import JSONDict

__all__ = (
    "JobFilePaths",
    "JobFileStore",
)

LOGGER_NAME = "SoAI.core.ipc.job_files"


@dataclass(frozen=True, slots=True)
class JobFilePaths:
    job_path: str
    response_path: str


class JobFileStore:
    def __init__(
        self,
        *,
        base_dir: str,
        ttl_sec: float,
        storage_manager: StorageManagerProtocol,
    ) -> None:
        base_value = os.path.abspath(str(base_dir or "").strip())
        if not base_value:
            raise ValidationError("base_dir is required for JobFileStore.")
        if storage_manager is None:
            raise ValidationError("storage_manager is required for JobFileStore.")
        ttl_value = float(ttl_sec)
        if ttl_value <= 0:
            raise ValidationError("ttl_sec must be positive.")
        self._base_dir = base_value
        self._ttl_sec = ttl_value
        self._storage_manager = storage_manager

    @property
    def base_dir(self) -> str:
        return self._base_dir

    async def ensure_dirs(self) -> None:
        await asyncio.to_thread(os.makedirs, self._base_dir, 0o755, True)

    def build_paths(self, request_id: str) -> JobFilePaths:
        normalized = str(request_id or "").strip()
        if not normalized:
            raise ValidationError("request_id is required to build job file paths.")
        token = uuid.uuid4().hex
        job_path = os.path.join(self._base_dir, f"{normalized}.{token}.job.json")
        response_path = os.path.join(self._base_dir, f"{normalized}.{token}.response.json")
        return JobFilePaths(job_path=job_path, response_path=response_path)

    async def write_job(self, path: str, job: JSONDict) -> None:
        if not isinstance(job, dict):
            raise ValidationError("job must be a JSON object.")
        content = serialize_json_compact_stable_strict(job, ensure_ascii=False)
        required_bytes = len(content.encode("utf-8"))
        with self._storage_manager.reserve_disk_space(
            path=path,
            required_bytes=required_bytes,
            operation="core.ipc.job_files.write_job",
            details={"path": path, "required_bytes": required_bytes},
        ) as reservation:
            with claim_reserved_write(reservation, size_bytes=required_bytes):
                await asyncio.to_thread(atomic_write_text_content, path, content, errors="replace")

    async def read_json_dict(self, path: str) -> JSONDict:
        normalized = str(path or "").strip()
        if not normalized:
            raise ValidationError("path is required.")
        try:
            text = await asyncio.to_thread(_read_text_file, normalized)
        except FileNotFoundError as exception:
            raise ValidationError("IPC response file missing.") from exception
        try:
            parsed = parse_json_value(text)
        except ValidationError as exception:
            raise ValidationError("IPC response file is not valid JSON.") from exception
        if not isinstance(parsed, dict):
            raise ValidationError("IPC response must be a JSON object.")
        return parsed

    async def sweep_orphaned_files(self) -> int:
        logger = get_logger(LOGGER_NAME)
        now = epoch_seconds_float()
        removed = 0
        try:
            entries = await asyncio.to_thread(os.listdir, self._base_dir)
        except FileNotFoundError:
            return 0
        for name in entries:
            if not isinstance(name, str):
                continue
            if (
                ".job.json" not in name
                and ".response.json" not in name
                and ".partial." not in name
                and not name.endswith(".cancel")
            ):
                continue
            full_path = os.path.join(self._base_dir, name)
            try:
                stat = await asyncio.to_thread(os.stat, full_path)
            except FileNotFoundError:
                continue
            age = now - float(stat.st_mtime)
            if age < self._ttl_sec:
                continue
            try:
                await asyncio.to_thread(os.remove, full_path)
                removed += 1
            except OSError as exception:
                logger.debug(
                    "Failed to remove orphaned IPC file: %s (%s)",
                    full_path,
                    str(exception),
                )
                continue
        return removed


def _read_text_file(path: str) -> str:
    with open_text(path, mode="r", encoding="utf-8", errors="strict") as handle:
        return handle.read()
