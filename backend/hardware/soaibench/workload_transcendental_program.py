"""SoAI - Shared SoAIBench transcendental OpenCL program [backend/hardware/soaibench/workload_transcendental_program.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("TRANSCENDENTAL_KERNEL_NAME", "TRANSCENDENTAL_KERNEL_SOURCE")

TRANSCENDENTAL_KERNEL_NAME = "soaibench_compute"
TRANSCENDENTAL_KERNEL_SOURCE = """
__kernel void soaibench_compute(__global float *data, const uint rounds) {
    const size_t gid = get_global_id(0);
    float value = 0.001f + (float)(gid & 1023) * 0.0001f;
    for (uint i = 0; i < rounds; i++) {
        value = fma(value, 1.000001f, 0.000001f);
        value = sin(value) + cos(value * 0.5f) + sqrt(fabs(value) + 1.0f);
    }
    data[gid] = value;
}
"""
