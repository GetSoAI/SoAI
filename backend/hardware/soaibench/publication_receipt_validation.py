"""SoAI - SoAIBench publication receipt contract [backend/hardware/soaibench/publication_receipt_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

from core.errors.exceptions import ApiError, ValidationError
from core.types.json import JSONDict
from core.validation.integers import is_strict_int
from core.validation.object_fields import require_exact_json_fields

__all__ = ("validate_publication_receipt",)


def validate_publication_receipt(receipt: JSONDict, expected_score: int) -> JSONDict:
    fields = {
        "submission_id",
        "public_url",
        "score_version",
        "overall_score",
        "validation",
        "duplicate",
    }
    try:
        require_exact_json_fields(
            receipt,
            allowed_fields=fields,
            label="SoAI Bench publication response",
        )
    except ValidationError as exception:
        raise ApiError(
            "SoAI Bench publication response is invalid.",
            code="soaibench_publication_invalid_response",
            http_status=502,
        ) from exception
    submission_id = receipt.get("submission_id")
    duplicate = receipt.get("duplicate")
    overall_score = receipt.get("overall_score")
    has_valid_identity = (
        isinstance(submission_id, str)
        and re.fullmatch(r"sb_[A-Za-z0-9_-]{22}", submission_id) is not None
        and receipt.get("public_url")
        == f"https://soai.to/soaibench-leaderboard/results/{submission_id}"
    )
    has_valid_score = (
        receipt.get("score_version") == "soaibench-v2"
        and is_strict_int(overall_score)
        and overall_score == expected_score
        and receipt.get("validation") in {"validated", "flagged"}
    )
    has_valid_delivery = isinstance(duplicate, bool)
    if not has_valid_identity or not has_valid_score or not has_valid_delivery:
        raise ApiError(
            "SoAI Bench publication response is inconsistent.",
            code="soaibench_publication_invalid_response",
            http_status=502,
        )
    return receipt
