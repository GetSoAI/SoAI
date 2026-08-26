/* SoAI - SoAI Bench GPU control contracts [frontend/assets/ts/pages/hardware/controllers/gpucontrol/soaibench/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GpuSoAIBenchRun } from '@core/api/contracts/hardwareContracts.ts';

type GpuSoAIBenchProfile = 'standard' | 'stress';
type GpuSoAIBenchBenchmarkMode = 'quick' | 'certified';

interface GpuSoAIBenchStartPayload {
    profile: GpuSoAIBenchProfile;
    benchmarkMode?: GpuSoAIBenchBenchmarkMode;
    temperatureLimitCelsius?: number;
}

interface GpuSoAIBenchRunLookupPayload {
    limit: number;
}

type GpuSoAIBenchRunRecord = GpuSoAIBenchRun;

export type { GpuSoAIBenchBenchmarkMode, GpuSoAIBenchProfile, GpuSoAIBenchRunLookupPayload, GpuSoAIBenchRunRecord, GpuSoAIBenchStartPayload };
