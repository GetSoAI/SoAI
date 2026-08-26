/* SoAI - Shared frontend API contract boundary hardware SoAI bench types [frontend/assets/ts/core/api/contracts/hardwareSoAIBenchTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { OpaqueJsonObject } from '@core/api/contracts/opaquePayload.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

interface GpuSoAIBenchStartRequest {
    profile: 'standard' | 'stress';
    benchmarkMode?: 'quick' | 'certified' | undefined;
    temperatureLimitCelsius?: number | undefined;
}

interface GpuIdentity {
    deviceId?: string | undefined;
    gpuName?: string | undefined;
    gpuModelKey?: string | undefined;
    vendor?: string | undefined;
    driverVersion?: string | undefined;
    gpuUuid?: string | undefined;
    pciBdf?: string | undefined;
    kernelDriver?: string | undefined;
    operatingSystem?: string | undefined;
    gpuIndex?: number | undefined;
}

interface GpuSoAIBenchSettingsSnapshot {
    powerLimitWatts?: number | null;
    fanSpeed?: number | null;
    coreClockMhz?: number | null;
    memClockMhz?: number | null;
}

type GpuSoAIBenchMetricFields = {
    overallScore?: number | null | undefined;
    computeScore?: number | null | undefined;
    computeGops?: number | null | undefined;
    aluGops?: number | null | undefined;
    matrixGops?: number | null | undefined;
    memoryScore?: number | null | undefined;
    memoryGbs?: number | null | undefined;
    latencyScore?: number | null | undefined;
    latencyUs?: number | null | undefined;
    latencyDispatchesPerSecond?: number | null | undefined;
    durationMs?: number | null | undefined;
    sampleCount?: number | null | undefined;
    maxTemperatureCelsius?: number | null | undefined;
    avgPowerWatts?: number | null | undefined;
    maxPowerWatts?: number | null | undefined;
    coreUtilizationPercent?: number | null | undefined;
    scoreVariancePercent?: number | null | undefined;
};

type GpuSoAIBenchScore = JsonObject &
    GpuSoAIBenchMetricFields & {
        scoreVersion?: string | null;
        stabilityMultiplier?: number | null;
        throttleDetected?: boolean | null;
        telemetryAvailable?: boolean | null;
        unavailableSensors?: string[] | null;
        failureReason?: string | null;
        scoreConfidence?: string | null;
    };

type GpuSoAIBenchSummary = JsonObject &
    GpuSoAIBenchMetricFields & {
        benchmarkMode?: string | null;
        temperatureLimitCelsius?: number | null;
        temperatureCelsius?: number | null;
        powerDrawWatts?: number | null;
        utilization?: number | null;
        telemetryAvailable?: boolean | null;
        throttleDetected?: boolean | null;
        unavailableSensors?: string[] | null;
        warmupPassesCompleted?: number | null;
        measuredPassesCompleted?: number | null;
        currentPassType?: string | null;
        currentPassIndex?: number | null;
        currentPassTotal?: number | null;
        currentPhase?: string | null;
        currentPhaseIndex?: number | null;
        currentPhaseTotal?: number | null;
        progressPercent?: number | null;
        stressSampleCount?: number | null;
        temperatureWarning?: string | null;
        matchBasis?: string | null;
        queueApi?: string | null;
        openclPlatformName?: string | null;
        openclPlatformVendor?: string | null;
        openclDeviceName?: string | null;
        openclDeviceVendor?: string | null;
        openclDriverVersion?: string | null;
        openclGlobalMemBytes?: number | null;
        openclMaxAllocBytes?: number | null;
        leaderboardEligible?: boolean | null;
        leaderboardRejectionReason?: string | null;
        scoreConfidence?: string | null;
        message?: string | null;
        guidance?: string | null;
    };

interface GpuSoAIBenchRun {
    runId?: string | undefined;
    taskId?: string | null | undefined;
    deviceId?: string | undefined;
    profile?: string | undefined;
    benchmarkMode?: string | undefined;
    status?: string | undefined;
    active?: boolean | undefined;
    accepted?: boolean | undefined;
    unsupportedReason?: string | null | undefined;
    failureReason?: string | null | undefined;
    leaderboardEligible?: boolean | undefined;
    leaderboardRejectionReason?: string | null | undefined;
    scoreVariancePercent?: number | null | undefined;
    matchBasis?: string | null | undefined;
    startedAtMs?: number | null | undefined;
    completedAtMs?: number | null | undefined;
    lastHeartbeatAtMs?: number | null | undefined;
    stopRequestedAtMs?: number | null | undefined;
    updateSeq?: number | undefined;
    gpuIdentity?: GpuIdentity | undefined;
    score?: GpuSoAIBenchScore | null | undefined;
    summary?: GpuSoAIBenchSummary | undefined;
    certification?: OpaqueJsonObject | undefined;
    environment?: OpaqueJsonObject | undefined;
    passes?: OpaqueJsonObject | undefined;
}

type GpuSoAIBenchHistoryRun = GpuSoAIBenchMetricFields & {
    runId: string;
    createdByUserId: number;
    createdByTool: string;
    deviceId: string;
    gpuName?: string | null | undefined;
    gpuModelKey?: string | null | undefined;
    vendor?: string | null | undefined;
    driverVersion?: string | null | undefined;
    gpuUuid?: string | null | undefined;
    pciBdf?: string | null | undefined;
    gpuIndex?: number | null | undefined;
    profile: string;
    benchmarkMode: string;
    status: string;
    scoreVersion?: string | null | undefined;
    stabilityMultiplier?: number | null | undefined;
    startedAtMs: number;
    completedAtMs?: number | null | undefined;
    lastHeartbeatAtMs?: number | null | undefined;
    stopRequestedAtMs?: number | null | undefined;
    updateSeq: number;
    settingsSnapshot: GpuSoAIBenchSettingsSnapshot;
    summary: GpuSoAIBenchSummary;
    passes: OpaqueJsonObject;
    environment: OpaqueJsonObject;
    certification: OpaqueJsonObject;
    leaderboardEligible: boolean;
    leaderboardRejectionReason?: string | null | undefined;
    failureReason?: string | null | undefined;
    unsupportedReason?: string | null | undefined;
    matchBasis?: string | null | undefined;
    staleHardware?: boolean | undefined;
    taskId?: string | null | undefined;
};

export type { GpuIdentity, GpuSoAIBenchHistoryRun, GpuSoAIBenchMetricFields, GpuSoAIBenchRun, GpuSoAIBenchScore, GpuSoAIBenchSettingsSnapshot, GpuSoAIBenchStartRequest, GpuSoAIBenchSummary };
