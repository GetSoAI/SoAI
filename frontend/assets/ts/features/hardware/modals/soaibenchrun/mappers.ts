/* SoAI - SoAI Bench run modal mapping [frontend/assets/ts/features/hardware/modals/soaibenchrun/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { decodeGpuSoAIBenchRun, serializeGpuSoAIBenchRun, type GpuSoAIBenchRun } from '@core/api/contracts/hardwareContracts.ts';
import type { DecodedSoAIBenchRun } from '@core/realtime/streammanager/resources/soaibenchRunsResource.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { SoAIBenchRunMetrics, SoAIBenchRunRecord } from '@features/hardware/modals/soaibenchrun/types.ts';
import { getSoAIBenchRunById, getSoAIBenchRunsForDevice } from '@features/hardware/soaibenchRunsIndex.ts';

const nullableInteger = (value: number | null | undefined): number | null => {
    return value === null || value === undefined ? null : Math.max(0, Math.trunc(value));
};

const nullableText = (value: string | null | undefined): string | null => {
    const text = toTrimmedString(value);
    return text || null;
};

const firstNumber = (...values: (number | null | undefined)[]): number | null => {
    for (const value of values) {
        if (value !== null && value !== undefined) return value;
    }
    return null;
};

const metricsFromRun = (run: GpuSoAIBenchRun): SoAIBenchRunMetrics => {
    const score = run.score ?? {};
    const summary = run.summary ?? {};
    return {
        overallScore: firstNumber(score.overallScore, summary.overallScore),
        computeScore: firstNumber(score.computeScore, summary.computeScore),
        computeGops: firstNumber(score.computeGops, summary.computeGops),
        aluGops: firstNumber(score.aluGops, summary.aluGops),
        matrixGops: firstNumber(score.matrixGops, summary.matrixGops),
        memoryScore: firstNumber(score.memoryScore, summary.memoryScore),
        memoryGbs: firstNumber(score.memoryGbs, summary.memoryGbs),
        latencyScore: firstNumber(score.latencyScore, summary.latencyScore),
        latencyUs: firstNumber(score.latencyUs, summary.latencyUs),
        latencyDispatchesPerSecond: firstNumber(score.latencyDispatchesPerSecond, summary.latencyDispatchesPerSecond),
        coreUtilizationPercent: firstNumber(score.coreUtilizationPercent, summary.coreUtilizationPercent, summary.utilization),
        maxTemperatureCelsius: firstNumber(score.maxTemperatureCelsius, summary.maxTemperatureCelsius, summary.temperatureCelsius),
        avgPowerWatts: firstNumber(score.avgPowerWatts, summary.avgPowerWatts, summary.powerDrawWatts),
        maxPowerWatts: firstNumber(score.maxPowerWatts, summary.maxPowerWatts),
        durationMs: firstNumber(score.durationMs, summary.durationMs),
        sampleCount: nullableInteger(score.sampleCount) ?? nullableInteger(summary.sampleCount),
        scoreVariancePercent: firstNumber(score.scoreVariancePercent, summary.scoreVariancePercent, run.scoreVariancePercent),
        warmupPassesCompleted: nullableInteger(summary.warmupPassesCompleted),
        measuredPassesCompleted: nullableInteger(summary.measuredPassesCompleted),
        currentPassType: nullableText(summary.currentPassType),
        currentPassIndex: nullableInteger(summary.currentPassIndex),
        currentPassTotal: nullableInteger(summary.currentPassTotal),
        currentPhase: nullableText(summary.currentPhase),
        currentPhaseIndex: nullableInteger(summary.currentPhaseIndex),
        currentPhaseTotal: nullableInteger(summary.currentPhaseTotal),
        progressPercent: firstNumber(summary.progressPercent)
    };
};

function presentRunRecord(value: DecodedSoAIBenchRun, raw: JsonObject): SoAIBenchRunRecord;
function presentRunRecord(value: GpuSoAIBenchRun, raw: JsonObject): SoAIBenchRunRecord | null;
function presentRunRecord(value: GpuSoAIBenchRun, raw: JsonObject): SoAIBenchRunRecord | null {
    const runId = toTrimmedString(value.runId);
    const deviceId = toTrimmedString(value.deviceId);
    const status = toTrimmedString(value.status);
    if (!runId || !deviceId || !status) {
        return null;
    }
    return {
        runId,
        deviceId,
        profile: toTrimmedString(value.profile) || 'standard',
        benchmarkMode: toTrimmedString(value.benchmarkMode) || 'quick',
        status,
        active: value.active === true || status === 'running',
        updateSeq: nullableInteger(value.updateSeq) ?? 0,
        leaderboardEligible: value.leaderboardEligible === true,
        leaderboardRejectionReason: nullableText(value.leaderboardRejectionReason),
        failureReason: nullableText(value.failureReason),
        unsupportedReason: nullableText(value.unsupportedReason),
        metrics: metricsFromRun(value),
        raw
    };
}

const normalizeRunRecord = (value: JsonValue | null | undefined): SoAIBenchRunRecord | null => {
    if (!isJsonObject(value)) return null;
    return presentRunRecord(decodeGpuSoAIBenchRun(value, 'SoAIBench run'), value);
};

const presentDecodedRunRecord = (value: DecodedSoAIBenchRun): SoAIBenchRunRecord => presentRunRecord(value, serializeGpuSoAIBenchRun(value));

const presentGpuSoAIBenchRun = (value: GpuSoAIBenchRun): SoAIBenchRunRecord | null => presentRunRecord(value, serializeGpuSoAIBenchRun(value));

const findRunById = (payload: JsonValue | null | undefined, runId: string): SoAIBenchRunRecord | null => {
    const run = getSoAIBenchRunById(payload, runId);
    return run ? presentDecodedRunRecord(run) : null;
};

const findActiveRunForDevice = (payload: JsonValue | null | undefined, deviceId: string): SoAIBenchRunRecord | null => {
    for (const value of getSoAIBenchRunsForDevice(payload, deviceId)) {
        const run = presentDecodedRunRecord(value);
        if (run.active) {
            return run;
        }
    }
    return null;
};

const findActiveStandardRunForDevice = (payload: JsonValue | null | undefined, deviceId: string): SoAIBenchRunRecord | null => {
    for (const value of getSoAIBenchRunsForDevice(payload, deviceId)) {
        const run = presentDecodedRunRecord(value);
        if (run.profile === 'standard' && run.benchmarkMode === 'certified' && run.active) {
            return run;
        }
    }
    return null;
};

const isTerminalSoAIBenchStatus = (status: string): boolean => {
    return status === 'completed' || status === 'failed' || status === 'unsupported' || status === 'unstable' || status === 'cancelled' || status === 'stopped' || status === 'indeterminate';
};

export { findActiveRunForDevice, findActiveStandardRunForDevice, findRunById, isTerminalSoAIBenchStatus, normalizeRunRecord, presentGpuSoAIBenchRun };
