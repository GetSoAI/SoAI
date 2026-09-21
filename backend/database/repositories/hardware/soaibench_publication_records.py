"""SoAI - SoAIBench publication record materialization [backend/database/repositories/hardware/soaibench_publication_records.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Literal

from core.errors.exceptions import StateError
from core.hardware.soaibench_publication import SoAIBenchPublicationRecord
from core.types.json import JSONDict
from core.validation.integers import is_strict_int
from database.repositories.hardware.soaibench_installation import (
    validate_soaibench_installation_id,
)

__all__ = ("materialize_soaibench_publication_record",)


def materialize_soaibench_publication_record(
    publication: JSONDict,
) -> SoAIBenchPublicationRecord:
    run_id = publication.get("run_id")
    user_id = publication.get("created_by_user_id")
    installation_id = validate_soaibench_installation_id(publication.get("installation_id"))
    canonical = publication.get("canonical_submission_json")
    prepared_at_ms = publication.get("prepared_at_ms")
    published_at_ms = publication.get("published_at_ms")
    if (
        not isinstance(run_id, str)
        or not is_strict_int(user_id)
        or not isinstance(canonical, str)
        or not is_strict_int(prepared_at_ms)
    ):
        raise StateError("SoAIBench publication row is invalid.")
    if published_at_ms is not None and not is_strict_int(published_at_ms):
        raise StateError("SoAIBench publication row is invalid.")
    raw_state = publication.get("state")
    state: Literal["prepared", "published"]
    if raw_state == "prepared":
        state = "prepared"
    elif raw_state == "published":
        state = "published"
    else:
        raise StateError("SoAIBench publication state is invalid.")
    receipt = publication.get("receipt")
    if receipt is not None and not isinstance(receipt, dict):
        raise StateError("SoAIBench publication receipt is invalid.")
    if state == "prepared" and (published_at_ms is not None or receipt is not None):
        raise StateError("Prepared SoAIBench publication row is inconsistent.")
    if state == "published" and (published_at_ms is None or receipt is None):
        raise StateError("Published SoAIBench publication row is inconsistent.")
    return SoAIBenchPublicationRecord(
        run_id=run_id,
        created_by_user_id=user_id,
        installation_id=installation_id,
        canonical_submission_json=canonical,
        state=state,
        prepared_at_ms=prepared_at_ms,
        published_at_ms=published_at_ms,
        receipt=receipt,
    )
