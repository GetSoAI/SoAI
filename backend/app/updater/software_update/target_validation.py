"""SoAI - Software update target validation [backend/app/updater/software_update/target_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.logging.protocols import LoggerProtocol

__all__ = ("validate_update_target",)


def validate_update_target(
    logger: LoggerProtocol,
    *,
    config_path: str,
    main_py_path: str | None,
) -> bool:
    required_paths = (config_path, main_py_path or "")
    missing = [path for path in required_paths if not path or not os.path.exists(path)]
    if missing:
        logger.error(
            "Refusing to update: expected SoAI installation artifacts are missing: %s",
            ", ".join(missing),
        )
        return False
    return True
