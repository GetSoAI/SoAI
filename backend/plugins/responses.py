"""SoAI - Plugin response factory functions [backend/plugins/responses.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from plugins.action_response import PluginActionResponse

__all__ = ("build_invalid_filename_response",)


def build_invalid_filename_response(exception: BaseException) -> PluginActionResponse:
    return PluginActionResponse(
        success=False,
        status_code=400,
        error_type="invalid_filename",
        error_message=str(exception),
    )
