/* SoAI - SoAI Bench history modal mapping [frontend/assets/ts/features/hardware/modals/soaibenchhistory/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import type { GpuOperationResponse, GpuSoAIBenchHistoryRun } from '@core/api/contracts/hardwareContracts.ts';
import { serializeGpuSoAIBenchHistoryRun } from '@core/api/contracts/hardwareSoAIBenchHistoryContracts.ts';
import type { SoAIBenchHistoryRun, SoAIBenchHistoryTelemetry } from '@features/hardware/modals/soaibenchhistory/types.ts';

const firstNullableNumber = (...values: (number | null | undefined)[]): number | null => {
    for (const value of values) {
        if (value !== null && value !== undefined) return value;
    }
    return null;
};

const nullableText = (value: string | null | undefined): string | null => {
    const text = toTrimmedString(value);
    return text || null;
};

const firstNullableText = (...values: (string | null | undefined)[]): string | null => {
    for (const value of values) {
        const parsed = nullableText(value);
        if (parsed !== null) {
            return parsed;
        }
    }
    return null;
};

const extractTelemetry = (run: GpuSoAIBenchHistoryRun): SoAIBenchHistoryTelemetry => {
    const summary = run.summary ?? {};
    return {
        overallScore: firstNullableNumber(run.overallScore, summary.overallScore),
        computeScore: firstNullableNumber(run.computeScore, summary.computeScore),
        memoryScore: firstNullableNumber(run.memoryScore, summary.memoryScore),
        aluGops: firstNullableNumber(run.aluGops, summary.aluGops),
        matrixGops: firstNullableNumber(run.matrixGops, summary.matrixGops),
        latencyScore: firstNullableNumber(run.latencyScore, summary.latencyScore),
        latencyUs: firstNullableNumber(run.latencyUs, summary.latencyUs),
        latencyDispatchesPerSecond: firstNullableNumber(run.latencyDispatchesPerSecond, summary.latencyDispatchesPerSecond),
        computeGops: firstNullableNumber(run.computeGops, summary.computeGops),
        memoryGbs: firstNullableNumber(run.memoryGbs, summary.memoryGbs),
        maxTemperatureCelsius: firstNullableNumber(summary.maxTemperatureCelsius, summary.temperatureCelsius),
        avgPowerWatts: firstNullableNumber(summary.avgPowerWatts),
        maxPowerWatts: firstNullableNumber(summary.maxPowerWatts),
        coreUtilizationPercent: firstNullableNumber(run.coreUtilizationPercent, summary.coreUtilizationPercent, summary.utilization),
        sampleCount: firstNullableNumber(run.sampleCount, summary.sampleCount)
    };
};

const normalizeHistoryRun = (value: GpuSoAIBenchHistoryRun): SoAIBenchHistoryRun => {
    const runId = toTrimmedString(value.runId);
    const profile = toTrimmedString(value.profile);
    const status = toTrimmedString(value.status);
    if (!runId) {
        throw new TypeError('SoAIBench history run must include run_id');
    }
    if (!profile) {
        throw new TypeError('SoAIBench history run must include profile');
    }
    if (!status) {
        throw new TypeError('SoAIBench history run must include status');
    }
    const summary = value.summary ?? {};
    return {
        runId,
        profile,
        benchmarkMode: firstNullableText(value.benchmarkMode, summary.benchmarkMode) || 'quick',
        status,
        startedAtMs: value.startedAtMs ?? null,
        durationMs: firstNullableNumber(value.durationMs, summary.durationMs),
        telemetry: extractTelemetry(value),
        leaderboardEligible: value.leaderboardEligible === true,
        leaderboardRejectionReason: firstNullableText(value.leaderboardRejectionReason, summary.leaderboardRejectionReason),
        scoreVariancePercent: firstNullableNumber(value.scoreVariancePercent, summary.scoreVariancePercent),
        phaseVariationPercent: summary.phaseVariationPercent ?? null,
        phaseDriftPercent: summary.phaseDriftPercent ?? null,
        warmupActiveSeconds: firstNullableNumber(summary.warmupActiveSeconds),
        legacy: value.legacyScore,
        publicationEligible: value.publicationEligible,
        settingsSnapshotAvailable: Object.keys(value.settingsSnapshot).length > 0,
        reasonMessage: nullableText(summary.message),
        guidanceMessage: nullableText(summary.guidance),
        failureReason: nullableText(value.failureReason),
        unsupportedReason: nullableText(value.unsupportedReason),
        matchBasis: firstNullableText(value.matchBasis, summary.matchBasis),
        staleHardware: value.staleHardware === true,
        raw: serializeGpuSoAIBenchHistoryRun(value)
    };
};

const normalizeHistoryRuns = (result: GpuOperationResponse): SoAIBenchHistoryRun[] => {
    if (!result.history) throw new TypeError('SoAIBench history result must include history');
    return result.history.map(normalizeHistoryRun);
};

export { normalizeHistoryRuns };
