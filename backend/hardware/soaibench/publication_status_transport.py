"""SoAI - SoAIBench published-result status transport [backend/hardware/soaibench/publication_status_transport.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

import httpx2

from core.errors.exceptions import ApiError, SoAIError, ValidationError
from core.serialization.json_parsing import parse_json_dict
from hardware.soaibench.publication_transport import PUBLICATION_URL, exchange_soaibench_json

__all__ = ("read_soaibench_publication_status",)


async def read_soaibench_publication_status(
    http_client: httpx2.AsyncClient, submission_id: str
) -> str:
    if re.fullmatch(r"sb_[A-Za-z0-9_-]{22}", submission_id) is None:
        raise ValidationError("SoAIBench submission ID is invalid.")
    request = http_client.build_request(
        "GET",
        f"{PUBLICATION_URL}/{submission_id}/status",
        headers={"Accept": "application/json", "Cache-Control": "no-store"},
        timeout=httpx2.Timeout(connect=5.0, pool=5.0, write=5.0, read=10.0),
    )
    _, raw, details = await exchange_soaibench_json(
        http_client, request, accepted_statuses=frozenset((200,))
    )
    try:
        document = parse_json_dict(
            raw, field="SoAIBench publication status", reject_duplicate_keys=True
        )
    except SoAIError as exception:
        raise ApiError(
            "SoAIBench publication status is invalid.",
            code="soaibench_publication_invalid_response",
            http_status=502,
            details=details,
        ) from exception
    state = document.get("state")
    if (
        set(document) != {"submission_id", "state"}
        or document.get("submission_id") != submission_id
        or not isinstance(state, str)
        or state not in {"validated", "flagged", "removed"}
    ):
        raise ApiError(
            "SoAIBench publication status is inconsistent.",
            code="soaibench_publication_invalid_response",
            http_status=502,
            details=details,
        )
    return state
