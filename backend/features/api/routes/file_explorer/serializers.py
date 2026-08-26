"""SoAI - File explorer response serialization logic [backend/features/api/routes/file_explorer/serializers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.files.explorer_models import BatchOperationResult

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_dual_path_response",
    "build_single_path_response",
    "serialize_batch_result",
)


def build_single_path_response(path: str) -> JSONDict:
    return {"status": "ok", "path": path}


def build_dual_path_response(source: str, destination: str) -> JSONDict:
    return {"status": "ok", "source": source, "destination": destination}


def serialize_batch_result(
    result: BatchOperationResult,
    destination_dir: str | None = None,
) -> JSONDict:
    response: JSONDict = {
        "status": "ok",
        "total": result.total,
        "succeeded": result.succeeded,
        "failed": result.failed,
        "results": [
            {
                "path": result_item.path,
                "success": result_item.success,
                "error": result_item.error_message,
            }
            for result_item in result.results
        ],
    }
    if destination_dir is not None:
        response["destination"] = destination_dir
    return response
