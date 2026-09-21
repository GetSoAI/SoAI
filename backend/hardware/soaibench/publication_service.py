"""SoAI - Durable idempotent SoAIBench publication flow [backend/hardware/soaibench/publication_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.singleflight import AsyncSingleflight
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ApiError, StateError, ValidationError
from core.serialization.json import (
    serialize_json_compact_stable,
    serialize_json_pretty_sorted_strict,
)
from core.serialization.json_parsing import parse_json_dict
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from hardware.soaibench.publication_document_validation import validate_publication_document
from hardware.soaibench.publication_projection import build_publication_document
from hardware.soaibench.publication_transport import (
    publish_to_soaibench,
    validate_publication_receipt,
)
from hardware.soaibench.publication_validation import validated_measured_passes

if TYPE_CHECKING:
    import httpx2

    from core.hardware.protocols_soaibench import DatabaseSoAIBenchProtocol
    from core.hardware.soaibench_publication import SoAIBenchPublicationRecord
    from core.logging.protocols import LoggerProtocol

__all__ = (
    "SoAIBenchPublicationService",
    "SoAIBenchPublicationServiceDependencies",
)

PUBLICATION_OPERATION = "hardware.soaibench.publication"


@dataclass(frozen=True, slots=True)
class SoAIBenchPublicationServiceDependencies:
    database_hardware: DatabaseSoAIBenchProtocol
    http_client: httpx2.AsyncClient
    logger: LoggerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="SoAIBenchPublicationServiceDependencies",
            database_hardware=self.database_hardware,
            http_client=self.http_client,
            logger=self.logger,
        )


class SoAIBenchPublicationService:
    def __init__(self, deps: SoAIBenchPublicationServiceDependencies) -> None:
        self._deps = deps
        self._singleflight: AsyncSingleflight[str, tuple[int, JSONDict]] = AsyncSingleflight()

    async def preview(self, *, run_id: str, user_id: int) -> JSONDict:
        if re.fullmatch(r"[0-9a-f]{32}", run_id) is None:
            raise ValidationError("SoAIBench run ID is invalid.")
        publication = await self._deps.database_hardware.get_soaibench_publication(
            user_id=user_id,
            run_id=run_id,
        )
        if publication is not None:
            document = _prepared_document(publication)
        else:
            run = await self._deps.database_hardware.get_soaibench_run_for_user(
                user_id=user_id,
                run_id=run_id,
            )
            if run is None:
                raise ValidationError("SoAIBench run was not found.")
            canonical = build_publication_document(run, validated_measured_passes(run))
            document = parse_json_dict(
                canonical, field="SoAIBench publication preview", reject_duplicate_keys=True
            )
        return {
            "projection_json": serialize_json_pretty_sorted_strict(document, ensure_ascii=False)
        }

    async def publish(self, *, run_id: str, user_id: int) -> tuple[int, JSONDict]:
        if re.fullmatch(r"[0-9a-f]{32}", run_id) is None:
            raise ValidationError("SoAIBench run ID is invalid.")
        await self._require_owned_source(run_id=run_id, user_id=user_id)
        return await self._singleflight.execute_or_wait(
            run_id,
            lambda: self._publish_once(run_id=run_id, user_id=user_id),
        )

    async def _require_owned_source(self, *, run_id: str, user_id: int) -> None:
        publication = await self._deps.database_hardware.get_soaibench_publication(
            user_id=user_id,
            run_id=run_id,
        )
        if publication is not None:
            return
        run = await self._deps.database_hardware.get_soaibench_run_for_user(
            user_id=user_id,
            run_id=run_id,
        )
        if run is None:
            raise ValidationError("SoAIBench run was not found.")

    async def _publish_once(self, *, run_id: str, user_id: int) -> tuple[int, JSONDict]:
        publication = await self._deps.database_hardware.get_soaibench_publication(
            user_id=user_id,
            run_id=run_id,
        )
        if publication is not None and publication.state == "published":
            receipt = publication.receipt
            if not isinstance(receipt, dict):
                raise StateError("Published SoAIBench receipt is missing.")
            score = _prepared_score(publication)
            validated_receipt = validate_publication_receipt(receipt, score)
            state = (
                "held_for_review"
                if validated_receipt.get("validation") == "flagged"
                else "already_published"
            )
            return 200, _local_receipt(validated_receipt, state)
        if publication is None:
            publication = await self._prepare(run_id=run_id, user_id=user_id)
        canonical, expected_score = _prepared_delivery(publication)
        try:
            upstream_status, receipt = await publish_to_soaibench(
                self._deps.http_client,
                canonical,
                run_id=run_id,
                expected_score=expected_score,
                installation_id=publication.installation_id,
            )
        except ApiError as exception:
            log_handled_exception(
                self._deps.logger,
                exception,
                message="SoAIBench publication request failed.",
                operation=PUBLICATION_OPERATION,
                details={"code": str(exception.code)},
                level="warning",
            )
            raise
        duplicate = receipt.get("duplicate") is True
        stored = await self._deps.database_hardware.finish_soaibench_publication(
            user_id=user_id,
            run_id=run_id,
            receipt_json=serialize_json_compact_stable(receipt),
            published_at_ms=epoch_ms(),
        )
        stored_receipt = stored.receipt
        if not isinstance(stored_receipt, dict):
            raise StateError("SoAIBench publication receipt was not persisted.")
        if stored_receipt.get("validation") == "flagged":
            state = "held_for_review"
        else:
            state = "already_published" if upstream_status == 200 or duplicate else "published"
        return (200 if upstream_status == 200 or duplicate else 201), _local_receipt(
            stored_receipt, state
        )

    async def _prepare(self, *, run_id: str, user_id: int) -> SoAIBenchPublicationRecord:
        run = await self._deps.database_hardware.get_soaibench_run_for_user(
            user_id=user_id,
            run_id=run_id,
        )
        if run is None:
            raise ValidationError("SoAIBench run was not found.")
        measured = validated_measured_passes(run)
        canonical = build_publication_document(run, measured)
        return await self._deps.database_hardware.prepare_soaibench_publication(
            user_id=user_id,
            run_id=run_id,
            canonical_submission_json=canonical,
            prepared_at_ms=epoch_ms(),
        )


def _local_receipt(receipt: JSONDict, state: str) -> JSONDict:
    return {
        "state": state,
        "submission_id": receipt.get("submission_id"),
        "public_url": receipt.get("public_url"),
        "score_version": receipt.get("score_version"),
        "overall_score": receipt.get("overall_score"),
        "validation": receipt.get("validation"),
        "duplicate": receipt.get("duplicate"),
    }


def _prepared_score(publication: SoAIBenchPublicationRecord) -> int:
    document = _prepared_document(publication)
    benchmark = document.get("benchmark")
    if not isinstance(benchmark, dict):
        raise StateError("Prepared SoAIBench publication benchmark is invalid.")
    score = benchmark.get("overall_score")
    if isinstance(score, bool) or not isinstance(score, int) or score < 0:
        raise StateError("Prepared SoAIBench publication score is invalid.")
    return score


def _prepared_delivery(publication: SoAIBenchPublicationRecord) -> tuple[bytes, int]:
    if publication.state != "prepared":
        raise StateError("Prepared SoAIBench publication state is invalid.")
    canonical = publication.canonical_submission_json
    if not isinstance(canonical, str):
        raise StateError("Prepared SoAIBench publication is incomplete.")
    _prepared_document(publication)
    return canonical.encode("utf-8"), _prepared_score(publication)


def _prepared_document(publication: SoAIBenchPublicationRecord) -> JSONDict:
    canonical = publication.canonical_submission_json
    if not isinstance(canonical, str):
        raise StateError("Prepared SoAIBench publication document is missing.")
    try:
        document = parse_json_dict(
            canonical, field="prepared SoAIBench publication", reject_duplicate_keys=True
        )
        validate_publication_document(document)
    except ValidationError as exception:
        raise StateError("Prepared SoAIBench publication document is invalid.") from exception
    if serialize_json_compact_stable(document, ensure_ascii=False) != canonical:
        raise StateError("Prepared SoAIBench publication document is not canonical.")
    return document
