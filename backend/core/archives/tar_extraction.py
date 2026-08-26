"""SoAI - Tar archive extraction helpers [backend/core/archives/tar_extraction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import shutil
import tarfile
from functools import partial

from core.archives.constants import MAX_SYMLINK_CHAIN_DEPTH, ensure_parent_exists
from core.archives.extraction_move import move_extracted_items
from core.archives.reservations import (
    DiskReservationRequest,
    open_disk_reservation,
    open_write_claim,
)
from core.archives.tar_plan import build_tar_extraction_plan
from core.archives.tar_plan_types import TarCopyOperation, TarExtractionPlan
from core.archives.tar_stream_budget import ResourceLimitedTarFile
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.files.temp_files import create_persistent_staging_directory
from core.filesystem.open_files import open_binary
from core.hardware.protocols_storage import DiskSpaceReservationProviderProtocol

__all__ = (
    "MAX_SYMLINK_CHAIN_DEPTH",
    "async_safe_tar_extractall",
    "safe_tar_extractall",
)


def safe_tar_extractall(
    archive_path: str,
    destination: str,
    *,
    reservation_provider: DiskSpaceReservationProviderProtocol,
) -> None:
    real_destination = os.path.realpath(destination)
    destination_parent = os.path.dirname(real_destination) or real_destination
    with open_binary(archive_path, mode="rb") as archive_handle:
        with ResourceLimitedTarFile.open(
            fileobj=archive_handle,
            mode="r|*",
        ) as planning_tar:
            plan = build_tar_extraction_plan(
                planning_tar,
                budget=planning_tar.planning_budget,
            )
        with open_disk_reservation(
            reservation_provider,
            requests=(
                DiskReservationRequest(
                    path=destination_parent,
                    required_bytes=plan.total_size,
                ),
            ),
            operation="core.archives.tar_extraction.extract",
            details={"archive_path": archive_path, "destination": real_destination},
        ) as reservation:
            with open_write_claim(reservation, size_bytes=plan.total_size) as claim:
                os.makedirs(destination, exist_ok=True)
                temp_dir = create_persistent_staging_directory(
                    prefix=".soai_tar_extract.",
                    directory=destination_parent,
                )
                try:
                    archive_handle.seek(0)
                    with ResourceLimitedTarFile.open(
                        fileobj=archive_handle,
                        mode="r:*",
                    ) as tar:
                        _extract_tar_plan(tar, plan, temp_dir)
                    move_extracted_items(temp_dir=temp_dir, destination=real_destination)
                finally:
                    if os.path.lexists(temp_dir):
                        shutil.rmtree(temp_dir)
                if claim is not None:
                    claim.commit()


def _extract_tar_plan(
    tar: tarfile.TarFile,
    plan: TarExtractionPlan,
    temp_dir: str,
) -> None:
    for directory in plan.directories:
        os.makedirs(os.path.join(temp_dir, directory), exist_ok=True)
    if plan.regular_members:
        tar.extractall(path=temp_dir, members=plan.regular_members, filter="data")
    for operation in plan.copy_operations:
        _execute_copy_operation(operation, temp_dir)


def _execute_copy_operation(operation: TarCopyOperation, temp_dir: str) -> None:
    source_path = os.path.join(temp_dir, operation.source_path)
    destination_path = os.path.join(temp_dir, operation.destination_path)
    ensure_parent_exists(destination_path)
    shutil.copy2(source_path, destination_path)


async def async_safe_tar_extractall(
    archive_path: str,
    destination: str,
    *,
    reservation_provider: DiskSpaceReservationProviderProtocol,
) -> None:
    await run_joined_thread_call(
        partial(
            safe_tar_extractall,
            archive_path,
            destination,
            reservation_provider=reservation_provider,
        ),
        task_name="safe-tar-extraction",
    )
