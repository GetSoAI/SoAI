"""SoAI - SoAIBench score and publication classification [backend/hardware/soaibench/classification.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.hardware.soaibench_score_fields import SOAIBENCH_MEASUREMENT_FIELDS
from core.types.json import JSONDict, JSONValue
from core.types.json_value import coerce_json_dict_or_empty
from core.validation.integers import is_strict_int
from core.validation.strict_numbers import require_finite_float_strict
from hardware.soaibench.publication_document_validation import PASS_FIELDS, TELEMETRY_FIELDS
from hardware.soaibench.publication_numeric_validation import has_public_certification_status
from hardware.soaibench.types import SOAIBENCH_SCORE_VERSION

__all__ = ("classify_run",)

LEGACY_SCORE_VERSION = "soaibench-v1"


def classify_run(run: JSONDict) -> JSONDict:
    score_version = run.get("score_version")
    current = score_version == SOAIBENCH_SCORE_VERSION
    legacy = score_version == LEGACY_SCORE_VERSION
    classification = "current" if current else "legacy" if legacy else "unsupported_legacy"
    return {
        "score_classification": classification,
        "legacy_score": not current,
        "publication_eligible": current and _is_publication_candidate(run),
    }


def _is_publication_candidate(run: JSONDict) -> bool:
    has_publishable_completion = (
        run.get("publication_source_supported") is True
        and run.get("status") == "completed"
        and run.get("profile") == "standard"
        and run.get("benchmark_mode") == "certified"
    )
    has_leaderboard_approval = (
        run.get("leaderboard_eligible") is True and run.get("leaderboard_rejection_reason") is None
    )
    if not has_publishable_completion or not has_leaderboard_approval:
        return False
    certification = coerce_json_dict_or_empty(run.get("certification"))
    if not has_public_certification_status(certification):
        return False
    passes = coerce_json_dict_or_empty(run.get("passes"))
    measured = passes.get("measured")
    return (
        _has_complete_public_run(run)
        and isinstance(measured, list)
        and len(measured) == 5
        and all(
            _has_complete_measured_pass(entry, index)
            for index, entry in enumerate(measured, start=1)
        )
    )


def _has_complete_public_run(run: JSONDict) -> bool:
    environment = coerce_json_dict_or_empty(run.get("environment"))
    opencl = coerce_json_dict_or_empty(environment.get("opencl"))
    summary = coerce_json_dict_or_empty(run.get("summary"))
    required_numbers = (*SOAIBENCH_MEASUREMENT_FIELDS, "score_variance_percent")
    return (
        all(_finite_number(run.get(field)) for field in required_numbers)
        and (_nonempty_text(run.get("gpu_name")) or _nonempty_text(run.get("gpu_model_key")))
        and all(
            _nonempty_text(environment.get(field)) for field in ("soai_version", "os", "cpu_name")
        )
        and _finite_number(environment.get("system_ram_gb"), positive=True)
        and _nonempty_text(opencl.get("device_name"))
        and all(field in summary for field in TELEMETRY_FIELDS)
    )


def _has_complete_measured_pass(entry: JSONValue, index: int) -> bool:
    if not isinstance(entry, dict):
        return False
    telemetry = coerce_json_dict_or_empty(entry.get("telemetry"))
    workload = coerce_json_dict_or_empty(entry.get("workload"))
    evidence = coerce_json_dict_or_empty(workload.get("workload_evidence"))
    return (
        is_strict_int(entry.get("index"))
        and entry.get("index") == index
        and entry.get("warmup") is False
        and entry.get("score_version") == SOAIBENCH_SCORE_VERSION
        and all(field in entry for field in PASS_FIELDS)
        and all(field in telemetry for field in TELEMETRY_FIELDS)
        and set(evidence) == {"alu", "compute", "matrix", "latency", "memory", "mixed"}
    )


def _finite_number(value: JSONValue, *, positive: bool = False) -> bool:
    try:
        number = require_finite_float_strict(value, error_message="SoAIBench evidence is invalid.")
    except ValidationError:
        return False
    return not positive or number > 0


def _nonempty_text(value: JSONValue) -> bool:
    return isinstance(value, str) and bool(value.strip())
