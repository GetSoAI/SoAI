"""SoAI - Instance control configuration reader [backend/app/cli/instance_control_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from app.config.io import ConfigIO, ConfigIODependencies
from core.config.value_validation import is_config_dict
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ConfigurationError
from core.filesystem.open_files import open_text
from core.logging.trace import get_logger

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict

__all__ = ()

LOGGER_NAME = "SoAI.app.cli.instance_control_config"
OPERATION = "app.cli.instance_control.load_config_dict"


def load_config_dict(config_path: str) -> ConfigDict | None:
    if not os.path.exists(config_path):
        return None
    try:
        with open_text(config_path, encoding="utf-8") as config_file:
            raw_contents = config_file.read()
        if not raw_contents.strip():
            return None
        config_io = ConfigIO(
            ConfigIODependencies(
                base_path=os.path.abspath(os.path.join(os.path.dirname(config_path), os.pardir)),
                core_config_path=config_path,
                plugins_path=None,
                lock_directory=None,
                logger=get_logger(LOGGER_NAME),
            ),
        )
        parsed = config_io.parse_config_contents(
            raw_contents,
            config_name="core",
            config_path=config_path,
        )
        if not is_config_dict(parsed):
            return None
        return parsed
    except (OSError, ConfigurationError) as error:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            error,
            message="Failed to read discovery host from config.yaml (non-critical).",
            operation=OPERATION,
            level="debug",
        )
        return None
