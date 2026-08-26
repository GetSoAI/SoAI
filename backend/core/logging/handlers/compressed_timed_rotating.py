"""SoAI - Time-based compressed rotating handler [backend/core/logging/handlers/compressed_timed_rotating.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import datetime
import logging
import os
import time
from logging.handlers import TimedRotatingFileHandler
from typing import override

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.formatter_support import (
    ROOT_LOGGER_NAME,
    normalize_compression_suffix,
)
from core.logging.handlers.log_compression import CompressionHelper
from core.timing.epoch import epoch_seconds

__all__ = ("CompressedTimedRotatingHandler",)

OPERATION = "log_manager.do_rollover"


class CompressedTimedRotatingHandler(TimedRotatingFileHandler):
    def __init__(
        self,
        filename: str,
        when: str = "h",
        interval: int = 1,
        backupCount: int = 0,
        encoding: str | None = None,
        delay: bool = False,
        utc: bool = False,
        atTime: datetime.time | None = None,
        errors: str | None = None,
        compress: bool = True,
        compression_suffix: str = ".gz",
    ) -> None:
        self.compress, self.compression_suffix = (
            compress,
            normalize_compression_suffix(compression_suffix),
        )
        self._compression = CompressionHelper(self)
        super().__init__(
            filename,
            when,
            interval,
            backupCount,
            encoding,
            delay,
            utc,
            atTime,
            errors,
        )

    @override
    def doRollover(self) -> None:
        try:
            if self.stream:
                self.stream.close()
            current_time = int(epoch_seconds())
            previous_rollover_time = self.rolloverAt - self.interval
            rollover_time_tuple = (
                time.gmtime(previous_rollover_time)
                if self.utc
                else time.localtime(previous_rollover_time)
            )
            destination_filename = self.rotation_filename(
                f"{self.baseFilename}.{time.strftime(self.suffix, rollover_time_tuple)}",
            )
            self._compression.remove_destination(destination_filename)
            self._compression.compress_and_rotate(self.baseFilename, destination_filename)
            if self.backupCount > 0:
                for file_path in self.getFilesToDelete():
                    try:
                        os.remove(file_path)
                    except OSError as deletion_error:
                        logging.getLogger(ROOT_LOGGER_NAME).warning(
                            "Failed to delete rotated log file '%s': %s",
                            file_path,
                            deletion_error,
                        )
            if not self.delay:
                self.stream = self._open()
            next_rollover = self.computeRollover(current_time)
            while next_rollover <= current_time:
                next_rollover += self.interval
            self.rolloverAt = next_rollover
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logging.getLogger(ROOT_LOGGER_NAME),
                exception,
                message=f"Log rotation failed critically for {self.baseFilename}: {exception}",
                operation=OPERATION,
                details={"file_path": self.baseFilename},
                level="critical",
            )
            raise

    @override
    def getFilesToDelete(self) -> list[str]:
        base_files = super().getFilesToDelete()
        if not self.compress:
            return base_files
        directory_name, base_name = os.path.split(self.baseFilename)
        directory_to_scan = directory_name or "."
        try:
            file_names = os.listdir(directory_to_scan)
        except (FileNotFoundError, NotADirectoryError):
            return base_files
        prefix = f"{base_name}."
        matches: list[str] = []
        for filename in file_names:
            if not filename.startswith(prefix):
                continue
            suffix = filename[len(prefix) :]
            suffix = suffix.removesuffix(self.compression_suffix)
            if self.extMatch.fullmatch(suffix):
                matches.append(os.path.join(directory_to_scan, filename))
        for file_path in base_files:
            if file_path not in matches:
                matches.append(file_path)
        if len(matches) <= self.backupCount:
            return []
        matches.sort()
        return matches[: len(matches) - self.backupCount]
