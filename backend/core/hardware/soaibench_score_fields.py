"""SoAI - Shared SoAIBench result metric identifiers [backend/core/hardware/soaibench_score_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "SOAIBENCH_COMPONENT_FIELDS",
    "SOAIBENCH_LATENCY_FIELDS",
    "SOAIBENCH_MEASUREMENT_FIELDS",
    "SOAIBENCH_SCORE_FIELDS",
    "SOAIBENCH_THROUGHPUT_FIELDS",
)

SOAIBENCH_COMPONENT_FIELDS = ("overall_score", "compute_score", "memory_score", "latency_score")
SOAIBENCH_THROUGHPUT_FIELDS = ("compute_gops", "alu_gops", "matrix_gops", "memory_gbs")
SOAIBENCH_LATENCY_FIELDS = ("latency_us", "latency_dispatches_per_second")
SOAIBENCH_SCORE_FIELDS = (
    *SOAIBENCH_COMPONENT_FIELDS,
    "stability_multiplier",
    *SOAIBENCH_THROUGHPUT_FIELDS,
    *SOAIBENCH_LATENCY_FIELDS,
)
SOAIBENCH_MEASUREMENT_FIELDS = (*SOAIBENCH_SCORE_FIELDS, "duration_ms", "sample_count")
