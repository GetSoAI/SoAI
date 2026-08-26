/* SoAI - Shared frontend API contract boundary hardware SoAI bench run contracts [frontend/assets/ts/core/api/contracts/hardwareSoAIBenchRunContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readOptionalHardwareNumber, readOptionalHardwareString } from '@core/api/contracts/hardwareContractReaders.ts';
import { decodeGpuSoAIBenchScore, serializeGpuSoAIBenchScore } from '@core/api/contracts/hardwareSoAIBenchScoreContracts.ts';
import { decodeGpuSoAIBenchSummary, serializeGpuSoAIBenchSummary } from '@core/api/contracts/hardwareSoAIBenchSummaryContracts.ts';
import type { GpuIdentity, GpuSoAIBenchRun } from '@core/api/contracts/hardwareSoAIBenchTypes.ts';
import { toJsonCompatibleObject } from '@core/primitives/clone.ts';
import { hasOwn, isNonNegativeInteger } from '@core/typeGuards.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { readNullableFiniteNumberValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableTrimmedStringValue, readRequiredBooleanValue } from '@core/types/payloadValueReaders.ts';

const optionalNullableNumber = (record: JsonObject, key: string, label: string): number | null | undefined => {
    if (!hasOwn(record, key)) return undefined;
    return readNullableFiniteNumberValue(record[key], `${label}.${key}`);
};

const optionalNullableString = (record: JsonObject, key: string, label: string): string | null | undefined => {
    if (!hasOwn(record, key)) return undefined;
    return readNullableTrimmedStringValue(record[key], `${label}.${key}`);
};

const optionalBoolean = (record: JsonObject, key: string, label: string): boolean | undefined => {
    if (!hasOwn(record, key)) return undefined;
    return readRequiredBooleanValue(record[key], `${label}.${key}`);
};

const optionalTimestamp = (record: JsonObject, key: string, label: string): number | null | undefined => {
    const value = optionalNullableNumber(record, key, label);
    if (value === undefined || value === null) return value;
    if (!Number.isSafeInteger(value) || value <= 0) throw new TypeError(`${label}.${key} must be a positive epoch millisecond integer or null`);
    return value;
};

const optionalSequence = (record: JsonObject, key: string, label: string): number | undefined => {
    const value = readOptionalHardwareNumber(record, key, label);
    if (value === undefined) return undefined;
    if (!isNonNegativeInteger(value)) throw new TypeError(`${label}.${key} must be a non-negative integer`);
    return value;
};

const decodeOpaqueObject = (value: JsonValue | undefined, label: string): JsonObject | undefined => {
    if (value === undefined || value === null) return undefined;
    return toJsonCompatibleObject(requireRecord(value, label));
};

const decodeGpuIdentity = (value: JsonValue | undefined, label: string): GpuIdentity | undefined => {
    if (value === undefined || value === null) return undefined;
    const record = requireRecord(value, label);
    return {
        deviceId: readOptionalHardwareString(record, 'device_id', label),
        gpuName: readOptionalHardwareString(record, 'gpu_name', label),
        gpuModelKey: readOptionalHardwareString(record, 'gpu_model_key', label),
        vendor: readOptionalHardwareString(record, 'vendor', label),
        driverVersion: readOptionalHardwareString(record, 'driver_version', label),
        gpuUuid: readOptionalHardwareString(record, 'gpu_uuid', label),
        pciBdf: readOptionalHardwareString(record, 'pci_bdf', label),
        kernelDriver: readOptionalHardwareString(record, 'kernel_driver', label),
        operatingSystem: readOptionalHardwareString(record, 'os', label),
        gpuIndex: readOptionalHardwareNumber(record, 'gpu_index', label)
    };
};

const decodeGpuSoAIBenchRun = (value: JsonValue, label: string): GpuSoAIBenchRun => {
    const record = requireRecord(value, label);
    return {
        runId: readOptionalHardwareString(record, 'run_id', label),
        taskId: optionalNullableString(record, 'task_id', label),
        deviceId: readOptionalHardwareString(record, 'device_id', label),
        profile: readOptionalHardwareString(record, 'profile', label),
        benchmarkMode: readOptionalHardwareString(record, 'benchmark_mode', label),
        status: readOptionalHardwareString(record, 'status', label),
        active: optionalBoolean(record, 'active', label),
        accepted: optionalBoolean(record, 'accepted', label),
        unsupportedReason: optionalNullableString(record, 'unsupported_reason', label),
        failureReason: optionalNullableString(record, 'failure_reason', label),
        leaderboardEligible: optionalBoolean(record, 'leaderboard_eligible', label),
        leaderboardRejectionReason: optionalNullableString(record, 'leaderboard_rejection_reason', label),
        scoreVariancePercent: optionalNullableNumber(record, 'score_variance_percent', label),
        matchBasis: optionalNullableString(record, 'match_basis', label),
        startedAtMs: optionalTimestamp(record, 'started_at_ms', label),
        completedAtMs: optionalTimestamp(record, 'completed_at_ms', label),
        lastHeartbeatAtMs: optionalTimestamp(record, 'last_heartbeat_at_ms', label),
        stopRequestedAtMs: optionalTimestamp(record, 'stop_requested_at_ms', label),
        updateSeq: optionalSequence(record, 'update_seq', label),
        gpuIdentity: decodeGpuIdentity(record['gpu_identity'], `${label}.gpu_identity`),
        score: decodeGpuSoAIBenchScore(record['score'], `${label}.score`),
        summary: decodeGpuSoAIBenchSummary(record['summary'], `${label}.summary`),
        certification: decodeOpaqueObject(record['certification'], `${label}.certification`),
        environment: decodeOpaqueObject(record['environment'], `${label}.environment`),
        passes: decodeOpaqueObject(record['passes'], `${label}.passes`)
    };
};

const serializeGpuIdentity = (identity: GpuIdentity): JsonObject => ({
    ...(identity.deviceId !== undefined ? { 'device_id': identity.deviceId } : {}),
    ...(identity.gpuName !== undefined ? { 'gpu_name': identity.gpuName } : {}),
    ...(identity.gpuModelKey !== undefined ? { 'gpu_model_key': identity.gpuModelKey } : {}),
    ...(identity.vendor !== undefined ? { vendor: identity.vendor } : {}),
    ...(identity.driverVersion !== undefined ? { 'driver_version': identity.driverVersion } : {}),
    ...(identity.gpuUuid !== undefined ? { 'gpu_uuid': identity.gpuUuid } : {}),
    ...(identity.pciBdf !== undefined ? { 'pci_bdf': identity.pciBdf } : {}),
    ...(identity.kernelDriver !== undefined ? { 'kernel_driver': identity.kernelDriver } : {}),
    ...(identity.operatingSystem !== undefined ? { os: identity.operatingSystem } : {}),
    ...(identity.gpuIndex !== undefined ? { 'gpu_index': identity.gpuIndex } : {})
});

const serializeGpuSoAIBenchRun = (run: GpuSoAIBenchRun): JsonObject => ({
    ...(run.runId !== undefined ? { 'run_id': run.runId } : {}),
    ...(run.taskId !== undefined ? { 'task_id': run.taskId } : {}),
    ...(run.deviceId !== undefined ? { 'device_id': run.deviceId } : {}),
    ...(run.profile !== undefined ? { profile: run.profile } : {}),
    ...(run.benchmarkMode !== undefined ? { 'benchmark_mode': run.benchmarkMode } : {}),
    ...(run.status !== undefined ? { status: run.status } : {}),
    ...(run.active !== undefined ? { active: run.active } : {}),
    ...(run.accepted !== undefined ? { accepted: run.accepted } : {}),
    ...(run.unsupportedReason !== undefined ? { 'unsupported_reason': run.unsupportedReason } : {}),
    ...(run.failureReason !== undefined ? { 'failure_reason': run.failureReason } : {}),
    ...(run.leaderboardEligible !== undefined ? { 'leaderboard_eligible': run.leaderboardEligible } : {}),
    ...(run.leaderboardRejectionReason !== undefined ? { 'leaderboard_rejection_reason': run.leaderboardRejectionReason } : {}),
    ...(run.scoreVariancePercent !== undefined ? { 'score_variance_percent': run.scoreVariancePercent } : {}),
    ...(run.matchBasis !== undefined ? { 'match_basis': run.matchBasis } : {}),
    ...(run.startedAtMs !== undefined ? { 'started_at_ms': run.startedAtMs } : {}),
    ...(run.completedAtMs !== undefined ? { 'completed_at_ms': run.completedAtMs } : {}),
    ...(run.lastHeartbeatAtMs !== undefined ? { 'last_heartbeat_at_ms': run.lastHeartbeatAtMs } : {}),
    ...(run.stopRequestedAtMs !== undefined ? { 'stop_requested_at_ms': run.stopRequestedAtMs } : {}),
    ...(run.updateSeq !== undefined ? { 'update_seq': run.updateSeq } : {}),
    ...(run.gpuIdentity !== undefined ? { 'gpu_identity': serializeGpuIdentity(run.gpuIdentity) } : {}),
    ...(run.score !== undefined ? { score: serializeGpuSoAIBenchScore(run.score) } : {}),
    ...(run.summary !== undefined ? { summary: serializeGpuSoAIBenchSummary(run.summary) } : {}),
    ...(run.certification !== undefined ? { certification: run.certification } : {}),
    ...(run.environment !== undefined ? { environment: run.environment } : {}),
    ...(run.passes !== undefined ? { passes: run.passes } : {})
});

export { decodeGpuSoAIBenchRun, serializeGpuSoAIBenchRun };
