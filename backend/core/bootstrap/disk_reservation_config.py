"""SoAI - Bootstrap disk reservation config resolution [backend/core/bootstrap/disk_reservation_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass

from core.bootstrap.config_scalars import read_yaml_scalar_key
from core.bootstrap.launcher_config import detect_config_path
from core.config.byte_sizes import require_config_mib_to_bytes
from core.config.numeric import coerce_positive_float
from core.config.path_resolution import resolve_path
from core.errors.exceptions import ValidationError
from core.timing.constants import CONTROL_TIMEOUT_SEC

__all__ = (
    "BootstrapDiskReservationConfig",
    "resolve_bootstrap_disk_reservation_config",
)

_DEFAULT_SYSTEM_DATA_PATH = "data"
_DEFAULT_LOCKS_PATH = "locks"
_DEFAULT_DISK_TOLERANCE_MB = "750"
_DEFAULT_LOCK_TIMEOUT_SEC = "10.0"


@dataclass(frozen=True, slots=True)
class BootstrapDiskReservationConfig:
    base_dir: str
    locks_dir: str
    tolerance_bytes: int
    lock_timeout_sec: float


def resolve_bootstrap_disk_reservation_config(
    repo_root_path: str,
) -> BootstrapDiskReservationConfig:
    base_dir = os.path.abspath(repo_root_path)
    config_path = detect_config_path(base_dir)
    system_data_path = _resolve_config_path(
        read_yaml_scalar_key(config_path, key="SYSTEM.PATHS.SYSTEM_DATA")
        or _DEFAULT_SYSTEM_DATA_PATH,
        base_dir,
    )
    locks_dir = _resolve_config_path(
        read_yaml_scalar_key(config_path, key="SYSTEM.PATHS.LOCKS") or _DEFAULT_LOCKS_PATH,
        system_data_path,
    )
    tolerance_raw = (
        read_yaml_scalar_key(config_path, key="SYSTEM.HARDWARE.DISK_FREE_SPACE_TOLERANCE_MB")
        or _DEFAULT_DISK_TOLERANCE_MB
    )
    lock_timeout_raw = (
        read_yaml_scalar_key(config_path, key="SYSTEM.HARDWARE.DISK_RESERVATION_LOCK_TIMEOUT_SEC")
        or _DEFAULT_LOCK_TIMEOUT_SEC
    )
    return BootstrapDiskReservationConfig(
        base_dir=base_dir,
        locks_dir=locks_dir,
        tolerance_bytes=require_config_mib_to_bytes(
            tolerance_raw,
            field="SYSTEM.HARDWARE.DISK_FREE_SPACE_TOLERANCE_MB",
            allow_zero=True,
            build_error=ValidationError,
        ),
        lock_timeout_sec=coerce_positive_float(
            lock_timeout_raw,
            default=CONTROL_TIMEOUT_SEC,
            minimum=0.1,
            label="SYSTEM.HARDWARE.DISK_RESERVATION_LOCK_TIMEOUT_SEC",
        ),
    )


def _resolve_config_path(path: str, base_path: str) -> str:
    resolved = resolve_path(path, base_path)
    if resolved is None:
        raise ValidationError("Bootstrap disk reservation path did not resolve.")
    return os.path.abspath(resolved)
