/* SoAI - SoAI Bench run modal mapping [frontend/assets/ts/features/hardware/modals/soaibenchrun/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { decodeGpuSoAIBenchRun, serializeGpuSoAIBenchRun, type GpuSoAIBenchRun } from '@core/api/contracts/hardwareContracts.ts';
import type { DecodedSoAIBenchRun } from '@core/realtime/streammanager/resources/soaibenchRunsResource.ts';
import { isArray } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { SoAIBenchRunMetrics, SoAIBenchRunRecord } from '@features/hardware/modals/soaibenchrun/types.ts';
import { getSoAIBenchRunsForDevice } from '@features/hardware/soaibenchRunsIndex.ts';

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

const measuredPassCountFromEvidence = (passes: GpuSoAIBenchRun['passes']): number | null => {
    const measured = passes?.['measured'];
    return isArray(measured) ? measured.length : null;
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
        phaseVariationPercent: summary.phaseVariationPercent ?? null,
        phaseDriftPercent: summary.phaseDriftPercent ?? null,
        warmupPassesCompleted: nullableInteger(summary.warmupPassesCompleted),
        warmupActiveSeconds: firstNumber(summary.warmupActiveSeconds),
        measuredPassesCompleted: nullableInteger(summary.measuredPassesCompleted) ?? measuredPassCountFromEvidence(run.passes),
        currentPassType: nullableText(summary.currentPassType),
        currentPassIndex: nullableInteger(summary.currentPassIndex),
        currentPassTotal: nullableInteger(summary.currentPassTotal),
        currentPhase: nullableText(summary.currentPhase),
        currentPhaseIndex: nullableInteger(summary.currentPhaseIndex),
        currentPhaseTotal: nullableInteger(summary.currentPhaseTotal),
        progressPercent: firstNumber(summary.progressPercent)
    };
};

interface SoAIBenchRunClassification {
    profile?: string | null | undefined;
    benchmarkMode?: string | null | undefined;
}

const resolveRunProfile = (value: SoAIBenchRunClassification): string => toTrimmedString(value.profile) || 'standard';

const resolveRunBenchmarkMode = (value: SoAIBenchRunClassification): string => toTrimmedString(value.benchmarkMode) || 'quick';

const isCertifiedSoAIBenchRun = (value: SoAIBenchRunClassification): boolean => resolveRunProfile(value) === 'standard' && resolveRunBenchmarkMode(value) === 'certified';

const isActiveSoAIBenchRun = (value: { active?: boolean | undefined; status?: string | undefined }): boolean => value.active === true || toTrimmedString(value.status) === 'running';

const isTerminalSoAIBenchStatus = (status: string): boolean => {
    return status === 'completed' || status === 'failed' || status === 'unsupported' || status === 'unstable' || status === 'cancelled' || status === 'stopped' || status === 'indeterminate';
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
    const summary = value.summary ?? {};
    const gpuIndex = value.gpuIdentity?.gpuIndex;
    return {
        runId,
        deviceId,
        gpuIndex: gpuIndex === undefined ? null : String(gpuIndex),
        gpuName: nullableText(value.gpuIdentity?.gpuName),
        profile: resolveRunProfile(value),
        benchmarkMode: resolveRunBenchmarkMode(value),
        status,
        startedAtMs: value.startedAtMs ?? null,
        stopRequestedAtMs: value.stopRequestedAtMs ?? null,
        active: isActiveSoAIBenchRun(value),
        updateSeq: nullableInteger(value.updateSeq) ?? 0,
        leaderboardEligible: value.leaderboardEligible === true,
        leaderboardRejectionReason: nullableText(value.leaderboardRejectionReason),
        legacy: value.legacyScore === true,
        publicationEligible: value.publicationEligible === true,
        matchBasis: nullableText(value.matchBasis),
        reasonMessage: nullableText(summary.message),
        guidanceMessage: nullableText(summary.guidance),
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

const findActiveRunForDevice = (payload: JsonValue | null | undefined, deviceId: string): DecodedSoAIBenchRun | null => {
    return getSoAIBenchRunsForDevice(payload, deviceId).find((run) => isActiveSoAIBenchRun(run)) ?? null;
};

export { findActiveRunForDevice, isActiveSoAIBenchRun, isCertifiedSoAIBenchRun, isTerminalSoAIBenchStatus, normalizeRunRecord, presentDecodedRunRecord };
