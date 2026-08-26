/* SoAI - Shared frontend API contract boundary hardware SoAI bench history contracts [frontend/assets/ts/core/api/contracts/hardwareSoAIBenchHistoryContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GpuSoAIBenchHistoryRun, GpuSoAIBenchSettingsSnapshot } from '@core/api/contracts/hardwareSoAIBenchTypes.ts';
import { readSoAIBenchOptionalNumber, readSoAIBenchOptionalString } from '@core/api/contracts/hardwareSoAIBenchReaders.ts';
import { decodeGpuSoAIBenchSummary, serializeGpuSoAIBenchSummary } from '@core/api/contracts/hardwareSoAIBenchSummaryContracts.ts';
import { toJsonCompatibleObject } from '@core/primitives/clone.ts';
import { hasOwn, isNonNegativeInteger } from '@core/typeGuards.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableTrimmedStringValue, readRequiredBooleanValue, readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';

const optionalText = (record: JsonObject, key: string, label: string): string | null | undefined => {
    if (!hasOwn(record, key)) return undefined;
    return readNullableTrimmedStringValue(record[key], `${label}.${key}`);
};

const optionalBoolean = (record: JsonObject, key: string, label: string): boolean | undefined => {
    if (!hasOwn(record, key)) return undefined;
    return readRequiredBooleanValue(record[key], `${label}.${key}`);
};

const requiredNonNegativeInteger = (record: JsonObject, key: string, label: string): number => {
    const value = readSoAIBenchOptionalNumber(record, key, label);
    if (!isNonNegativeInteger(value)) throw new TypeError(`${label}.${key} must be a non-negative integer`);
    return value;
};

const requiredPositiveTimestamp = (record: JsonObject, key: string, label: string): number => {
    const value = readSoAIBenchOptionalNumber(record, key, label);
    if (!Number.isSafeInteger(value) || value === null || value === undefined || value <= 0) throw new TypeError(`${label}.${key} must be a positive epoch millisecond integer`);
    return value;
};

const optionalTimestamp = (record: JsonObject, key: string, label: string): number | null | undefined => {
    const value = readSoAIBenchOptionalNumber(record, key, label);
    if (value === undefined || value === null) return value;
    if (!Number.isSafeInteger(value) || value <= 0) throw new TypeError(`${label}.${key} must be a positive epoch millisecond integer or null`);
    return value;
};

const decodeOpaqueObject = (value: JsonValue | undefined, label: string): JsonObject => {
    if (value === undefined || value === null) return {};
    return toJsonCompatibleObject(requireRecord(value, label));
};

const decodeSettingsSnapshot = (value: JsonValue | undefined, label: string): GpuSoAIBenchSettingsSnapshot => {
    if (value === undefined || value === null) return {};
    const record = requireRecord(value, label);
    if (hasOwn(record, 'powerLimitWatts') || hasOwn(record, 'coreClockMhz')) throw new TypeError(`${label} must use canonical V1 wire fields`);
    const settings: GpuSoAIBenchSettingsSnapshot = {};
    const powerLimitWatts = readSoAIBenchOptionalNumber(record, 'power_limit_watts', label);
    const fanSpeed = readSoAIBenchOptionalNumber(record, 'fan_speed', label);
    const coreClockMhz = readSoAIBenchOptionalNumber(record, 'core_clock_mhz', label);
    const memClockMhz = readSoAIBenchOptionalNumber(record, 'mem_clock_mhz', label);
    if (powerLimitWatts !== undefined) settings.powerLimitWatts = powerLimitWatts;
    if (fanSpeed !== undefined) settings.fanSpeed = fanSpeed;
    if (coreClockMhz !== undefined) settings.coreClockMhz = coreClockMhz;
    if (memClockMhz !== undefined) settings.memClockMhz = memClockMhz;
    return settings;
};

const decodeGpuSoAIBenchHistoryRun = (value: JsonValue, label: string): GpuSoAIBenchHistoryRun => {
    const record = requireRecord(value, label);
    if (hasOwn(record, 'runId') || hasOwn(record, 'createdByUserId') || hasOwn(record, 'overallScore') || hasOwn(record, 'settingsSnapshot') || hasOwn(record, 'staleHardware')) {
        throw new TypeError(`${label} must use canonical V1 wire fields`);
    }
    return {
        runId: readRequiredTrimmedStringValue(record['run_id'], `${label}.run_id`),
        createdByUserId: requiredNonNegativeInteger(record, 'created_by_user_id', label),
        createdByTool: readRequiredTrimmedStringValue(record['created_by_tool'], `${label}.created_by_tool`),
        deviceId: readRequiredTrimmedStringValue(record['device_id'], `${label}.device_id`),
        gpuName: optionalText(record, 'gpu_name', label),
        gpuModelKey: optionalText(record, 'gpu_model_key', label),
        vendor: optionalText(record, 'vendor', label),
        driverVersion: optionalText(record, 'driver_version', label),
        gpuUuid: optionalText(record, 'gpu_uuid', label),
        pciBdf: optionalText(record, 'pci_bdf', label),
        gpuIndex: readSoAIBenchOptionalNumber(record, 'gpu_index', label),
        profile: readRequiredTrimmedStringValue(record['profile'], `${label}.profile`),
        benchmarkMode: readRequiredTrimmedStringValue(record['benchmark_mode'], `${label}.benchmark_mode`),
        status: readRequiredTrimmedStringValue(record['status'], `${label}.status`),
        scoreVersion: optionalText(record, 'score_version', label),
        overallScore: readSoAIBenchOptionalNumber(record, 'overall_score', label),
        computeScore: readSoAIBenchOptionalNumber(record, 'compute_score', label),
        memoryScore: readSoAIBenchOptionalNumber(record, 'memory_score', label),
        latencyScore: readSoAIBenchOptionalNumber(record, 'latency_score', label),
        stabilityMultiplier: readSoAIBenchOptionalNumber(record, 'stability_multiplier', label),
        computeGops: readSoAIBenchOptionalNumber(record, 'compute_gops', label),
        aluGops: readSoAIBenchOptionalNumber(record, 'alu_gops', label),
        matrixGops: readSoAIBenchOptionalNumber(record, 'matrix_gops', label),
        memoryGbs: readSoAIBenchOptionalNumber(record, 'memory_gbs', label),
        latencyUs: readSoAIBenchOptionalNumber(record, 'latency_us', label),
        latencyDispatchesPerSecond: readSoAIBenchOptionalNumber(record, 'latency_dispatches_per_second', label),
        startedAtMs: requiredPositiveTimestamp(record, 'started_at_ms', label),
        completedAtMs: optionalTimestamp(record, 'completed_at_ms', label),
        lastHeartbeatAtMs: optionalTimestamp(record, 'last_heartbeat_at_ms', label),
        stopRequestedAtMs: optionalTimestamp(record, 'stop_requested_at_ms', label),
        updateSeq: requiredNonNegativeInteger(record, 'update_seq', label),
        durationMs: readSoAIBenchOptionalNumber(record, 'duration_ms', label),
        sampleCount: readSoAIBenchOptionalNumber(record, 'sample_count', label),
        settingsSnapshot: decodeSettingsSnapshot(record['settings_snapshot'], `${label}.settings_snapshot`),
        summary: decodeGpuSoAIBenchSummary(record['summary'], `${label}.summary`) ?? {},
        passes: decodeOpaqueObject(record['passes'], `${label}.passes`),
        environment: decodeOpaqueObject(record['environment'], `${label}.environment`),
        certification: decodeOpaqueObject(record['certification'], `${label}.certification`),
        leaderboardEligible: readRequiredBooleanValue(record['leaderboard_eligible'], `${label}.leaderboard_eligible`),
        leaderboardRejectionReason: optionalText(record, 'leaderboard_rejection_reason', label),
        scoreVariancePercent: readSoAIBenchOptionalNumber(record, 'score_variance_percent', label),
        failureReason: optionalText(record, 'failure_reason', label),
        unsupportedReason: optionalText(record, 'unsupported_reason', label),
        matchBasis: readSoAIBenchOptionalString(record, 'match_basis', label),
        staleHardware: optionalBoolean(record, 'stale_hardware', label),
        taskId: optionalText(record, 'task_id', label)
    };
};

const serializeSettingsSnapshot = (settings: GpuSoAIBenchSettingsSnapshot): JsonObject => ({
    ...(settings.powerLimitWatts !== undefined ? { 'power_limit_watts': settings.powerLimitWatts } : {}),
    ...(settings.fanSpeed !== undefined ? { 'fan_speed': settings.fanSpeed } : {}),
    ...(settings.coreClockMhz !== undefined ? { 'core_clock_mhz': settings.coreClockMhz } : {}),
    ...(settings.memClockMhz !== undefined ? { 'mem_clock_mhz': settings.memClockMhz } : {})
});

const serializeGpuSoAIBenchHistoryRun = (run: GpuSoAIBenchHistoryRun): JsonObject => ({
    'run_id': run.runId,
    'created_by_user_id': run.createdByUserId,
    'created_by_tool': run.createdByTool,
    'device_id': run.deviceId,
    ...(run.gpuName !== undefined ? { 'gpu_name': run.gpuName } : {}),
    ...(run.gpuModelKey !== undefined ? { 'gpu_model_key': run.gpuModelKey } : {}),
    ...(run.vendor !== undefined ? { vendor: run.vendor } : {}),
    ...(run.driverVersion !== undefined ? { 'driver_version': run.driverVersion } : {}),
    ...(run.gpuUuid !== undefined ? { 'gpu_uuid': run.gpuUuid } : {}),
    ...(run.pciBdf !== undefined ? { 'pci_bdf': run.pciBdf } : {}),
    ...(run.gpuIndex !== undefined ? { 'gpu_index': run.gpuIndex } : {}),
    profile: run.profile,
    'benchmark_mode': run.benchmarkMode,
    status: run.status,
    ...(run.scoreVersion !== undefined ? { 'score_version': run.scoreVersion } : {}),
    ...(run.overallScore !== undefined ? { 'overall_score': run.overallScore } : {}),
    ...(run.computeScore !== undefined ? { 'compute_score': run.computeScore } : {}),
    ...(run.memoryScore !== undefined ? { 'memory_score': run.memoryScore } : {}),
    ...(run.latencyScore !== undefined ? { 'latency_score': run.latencyScore } : {}),
    ...(run.stabilityMultiplier !== undefined ? { 'stability_multiplier': run.stabilityMultiplier } : {}),
    ...(run.computeGops !== undefined ? { 'compute_gops': run.computeGops } : {}),
    ...(run.aluGops !== undefined ? { 'alu_gops': run.aluGops } : {}),
    ...(run.matrixGops !== undefined ? { 'matrix_gops': run.matrixGops } : {}),
    ...(run.memoryGbs !== undefined ? { 'memory_gbs': run.memoryGbs } : {}),
    ...(run.latencyUs !== undefined ? { 'latency_us': run.latencyUs } : {}),
    ...(run.latencyDispatchesPerSecond !== undefined ? { 'latency_dispatches_per_second': run.latencyDispatchesPerSecond } : {}),
    'started_at_ms': run.startedAtMs,
    ...(run.completedAtMs !== undefined ? { 'completed_at_ms': run.completedAtMs } : {}),
    ...(run.lastHeartbeatAtMs !== undefined ? { 'last_heartbeat_at_ms': run.lastHeartbeatAtMs } : {}),
    ...(run.stopRequestedAtMs !== undefined ? { 'stop_requested_at_ms': run.stopRequestedAtMs } : {}),
    'update_seq': run.updateSeq,
    ...(run.durationMs !== undefined ? { 'duration_ms': run.durationMs } : {}),
    ...(run.sampleCount !== undefined ? { 'sample_count': run.sampleCount } : {}),
    'settings_snapshot': serializeSettingsSnapshot(run.settingsSnapshot),
    summary: serializeGpuSoAIBenchSummary(run.summary),
    passes: run.passes,
    environment: run.environment,
    certification: run.certification,
    'leaderboard_eligible': run.leaderboardEligible,
    ...(run.leaderboardRejectionReason !== undefined ? { 'leaderboard_rejection_reason': run.leaderboardRejectionReason } : {}),
    ...(run.scoreVariancePercent !== undefined ? { 'score_variance_percent': run.scoreVariancePercent } : {}),
    ...(run.failureReason !== undefined ? { 'failure_reason': run.failureReason } : {}),
    ...(run.unsupportedReason !== undefined ? { 'unsupported_reason': run.unsupportedReason } : {}),
    ...(run.matchBasis !== undefined ? { 'match_basis': run.matchBasis } : {}),
    ...(run.staleHardware !== undefined ? { 'stale_hardware': run.staleHardware } : {}),
    ...(run.taskId !== undefined ? { 'task_id': run.taskId } : {})
});

export { decodeGpuSoAIBenchHistoryRun, serializeGpuSoAIBenchHistoryRun };
