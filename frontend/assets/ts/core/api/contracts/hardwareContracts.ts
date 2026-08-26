/* SoAI - Frontend hardware API boundary contracts [frontend/assets/ts/core/api/contracts/hardwareContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { decodeHardwareNumberArray, decodeHardwareStringArray, readOptionalHardwareString } from '@core/api/contracts/hardwareContractReaders.ts';
import { decodeRawResponse } from '@core/api/contracts/systemContracts.ts';
import { decodeHardwareCapabilities, decodeHardwareSnapshot } from '@core/api/contracts/hardwareSnapshotContracts.ts';
import { decodeGpuSoAIBenchHistoryRun } from '@core/api/contracts/hardwareSoAIBenchHistoryContracts.ts';
import { decodeGpuSoAIBenchRun, serializeGpuSoAIBenchRun } from '@core/api/contracts/hardwareSoAIBenchRunContracts.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableFiniteNumberValue, readRequiredFiniteNumberValue } from '@core/types/payloadNumberReaders.ts';
import { readNullableTrimmedStringValue, readRequiredBooleanValue, readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import { hasOwn } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { GpuIdentity, GpuOperationResponse, GpuSettingValue, GpuSettingsUpdateRequest, GpuSlotStoreRequest, GpuSoAIBenchHistoryRun, GpuSoAIBenchRun, GpuSoAIBenchStartRequest, HardwareCapabilitiesResponse, HardwareGpuSnapshot, HardwareHistoryConfiguration, HardwareHistoryMetadata, HardwareHistoryResponse, HardwareMemorySnapshot, HardwareNetworkInterface, HardwareNetworkSpeed, HardwareSnapshotResponse, HardwareSummary, HardwareVolumeSnapshot, KillProcessResponse } from '@core/api/contracts/hardwareContractTypes.ts';

type GpuTextField = 'code' | 'status' | 'failure_reason' | 'unsupported_reason' | 'run_id' | 'profile';

const GPU_TEXT_FIELDS: readonly GpuTextField[] = ['code', 'status', 'failure_reason', 'unsupported_reason', 'run_id', 'profile'];

const GPU_TEXT_FIELD_ASSIGNERS: Readonly<Record<GpuTextField, (response: GpuOperationResponse, value: string) => void>> = {
    code: (response, value): void => {
        response.code = value;
    },
    status: (response, value): void => {
        response.status = value;
    },
    'failure_reason': (response, value): void => {
        response.failureReason = value;
    },
    'unsupported_reason': (response, value): void => {
        response.unsupportedReason = value;
    },
    'run_id': (response, value): void => {
        response.runId = value;
    },
    profile: (response, value): void => {
        response.profile = value;
    }
};

const decodeOptionalObject = (value: JsonValue | undefined, label: string): JsonObject | undefined => (value === undefined || value === null ? undefined : requireRecord(value, label));

const decodeGpuSettingValue = (value: JsonValue | undefined, label: string): GpuSettingValue | undefined => {
    if (value === undefined) return undefined;
    if (value === null || value === 'auto') return value;
    return readRequiredFiniteNumberValue(value, label);
};

const decodeGpuSettings = (value: JsonValue | undefined, label: string): GpuSettingsUpdateRequest | undefined => {
    if (value === undefined || value === null) return undefined;
    const record = requireRecord(value, label);
    const settings: GpuSettingsUpdateRequest = {};
    const powerLimit = decodeGpuSettingValue(record['power_limit'], `${label}.power_limit`);
    const coreClock = decodeGpuSettingValue(record['core_clock'], `${label}.core_clock`);
    const memClock = decodeGpuSettingValue(record['mem_clock'], `${label}.mem_clock`);
    const fanSpeed = decodeGpuSettingValue(record['fan_speed'], `${label}.fan_speed`);
    if (powerLimit !== undefined) settings.powerLimit = powerLimit;
    if (coreClock !== undefined) settings.coreClock = coreClock;
    if (memClock !== undefined) settings.memClock = memClock;
    if (fanSpeed !== undefined) settings.fanSpeed = fanSpeed;
    if (record['reset_clocks'] !== undefined) settings.resetClocks = readRequiredBooleanValue(record['reset_clocks'], `${label}.reset_clocks`);
    return settings;
};

const decodeGpuFieldModes = (value: JsonValue | undefined, label: string): GpuSlotStoreRequest['fieldModes'] => {
    if (value === undefined || value === null) return undefined;
    const record = requireRecord(value, label);
    const readMode = (key: string): 'auto' | 'manual' | undefined => {
        const mode = record[key];
        if (mode === undefined) return undefined;
        if (mode !== 'auto' && mode !== 'manual') throw new TypeError(`${label}.${key} must be auto or manual`);
        return mode;
    };
    const fieldModes: NonNullable<GpuSlotStoreRequest['fieldModes']> = {};
    const powerLimit = readMode('power_limit');
    const coreClock = readMode('core_clock');
    const memClock = readMode('mem_clock');
    const fanSpeed = readMode('fan_speed');
    if (powerLimit !== undefined) fieldModes.powerLimit = powerLimit;
    if (coreClock !== undefined) fieldModes.coreClock = coreClock;
    if (memClock !== undefined) fieldModes.memClock = memClock;
    if (fanSpeed !== undefined) fieldModes.fanSpeed = fanSpeed;
    return fieldModes;
};

const decodeObjectArray = (value: JsonValue | undefined, label: string): JsonObject[] => {
    if (!Array.isArray(value)) throw new TypeError(`${label} must be an array`);
    return value.map((entry, index) => requireRecord(entry, `${label}[${String(index)}]`));
};

const decodeGpuOperationResponse = (value: ApiResponsePayload): GpuOperationResponse => {
    const record = requireRecord(value, 'Hardware GPU response');
    const response: GpuOperationResponse = {};
    if (typeof record['success'] === 'boolean') response.success = record['success'];
    if (typeof record['accepted'] === 'boolean') response.accepted = record['accepted'];
    if (typeof record['active'] === 'boolean') response.active = record['active'];
    for (const key of GPU_TEXT_FIELDS) {
        const field = readOptionalHardwareString(record, key, 'Hardware GPU response');
        if (field === undefined) continue;
        GPU_TEXT_FIELD_ASSIGNERS[key](response, field);
    }
    const runs = record['runs'];
    if (runs !== undefined && runs !== null) {
        if (!Array.isArray(runs)) throw new TypeError('Hardware GPU response.runs must be an array');
        response.runs = runs.map((entry, index) => decodeGpuSoAIBenchRun(entry, `Hardware GPU response.runs[${String(index)}]`));
    }
    const history = record['history'];
    if (history !== undefined && history !== null) {
        if (!Array.isArray(history)) throw new TypeError('Hardware GPU response.history must be an array');
        response.history = history.map((entry, index) => decodeGpuSoAIBenchHistoryRun(entry, `Hardware GPU response.history[${String(index)}]`));
    }
    const slotState = decodeOptionalObject(record['slot_state'], 'Hardware GPU response.slot_state');
    if (slotState) response.slotState = { settings: decodeGpuSettings(slotState['settings'], 'Hardware GPU response.slot_state.settings'), fieldModes: decodeGpuFieldModes(slotState['field_modes'], 'Hardware GPU response.slot_state.field_modes') };
    const boot = decodeOptionalObject(record['boot'], 'Hardware GPU response.boot');
    if (boot) response.boot = { enabled: boot['enabled'] === undefined ? undefined : readRequiredBooleanValue(boot['enabled'], 'Hardware GPU response.boot.enabled'), slot: boot['slot'] === undefined || boot['slot'] === null ? undefined : String(boot['slot']) };
    return response;
};

const decodeHardwareHistory = (value: ApiResponsePayload): HardwareHistoryResponse => {
    const record = requireRecord(value, 'Hardware history');
    const metadataRecord = requireRecord(record['metadata'], 'Hardware history.metadata');
    if (hasOwn(record, 'intervalMs') || hasOwn(record, 'timestampsMs') || hasOwn(metadataRecord, 'intervalMs')) throw new TypeError('Hardware history must use canonical V1 wire fields');
    const aggregation = readRequiredTrimmedStringValue(record['aggregation'], 'Hardware history.aggregation');
    const intervalMs = readRequiredFiniteNumberValue(record['interval_ms'], 'Hardware history.interval_ms');
    return {
        aggregation,
        intervalMs: intervalMs,
        timestampsMs: decodeHardwareNumberArray(record['timestamps_ms'], 'Hardware history.timestamps_ms') ?? [],
        metrics: decodeHardwareStringArray(record['metrics'], 'Hardware history.metrics') ?? [],
        data: decodeObjectArray(record['data'], 'Hardware history.data'),
        metadata: {
            aggregation: readRequiredTrimmedStringValue(metadataRecord['aggregation'], 'Hardware history.metadata.aggregation'),
            intervalMs: readRequiredFiniteNumberValue(metadataRecord['interval_ms'], 'Hardware history.metadata.interval_ms'),
            requestedIntervalMs: readNullableFiniteNumberValue(metadataRecord['requested_interval_ms'], 'Hardware history.metadata.requested_interval_ms'),
            intervalSource: readRequiredTrimmedStringValue(metadataRecord['interval_source'], 'Hardware history.metadata.interval_source'),
            startTsMs: readRequiredFiniteNumberValue(metadataRecord['start_ts_ms'], 'Hardware history.metadata.start_ts_ms'),
            requestedStartTsMs: readRequiredFiniteNumberValue(metadataRecord['requested_start_ts_ms'], 'Hardware history.metadata.requested_start_ts_ms'),
            endTsMs: readRequiredFiniteNumberValue(metadataRecord['end_ts_ms'], 'Hardware history.metadata.end_ts_ms'),
            requestedEndTsMs: readRequiredFiniteNumberValue(metadataRecord['requested_end_ts_ms'], 'Hardware history.metadata.requested_end_ts_ms'),
            alignedStartTsMs: readRequiredFiniteNumberValue(metadataRecord['aligned_start_ts_ms'], 'Hardware history.metadata.aligned_start_ts_ms'),
            alignedEndTsMs: readRequiredFiniteNumberValue(metadataRecord['aligned_end_ts_ms'], 'Hardware history.metadata.aligned_end_ts_ms'),
            durationMs: readRequiredFiniteNumberValue(metadataRecord['duration_ms'], 'Hardware history.metadata.duration_ms'),
            requestedDurationMs: readRequiredFiniteNumberValue(metadataRecord['requested_duration_ms'], 'Hardware history.metadata.requested_duration_ms'),
            points: readRequiredFiniteNumberValue(metadataRecord['points'], 'Hardware history.metadata.points'),
            requestedPoints: readRequiredFiniteNumberValue(metadataRecord['requested_points'], 'Hardware history.metadata.requested_points'),
            effectivePoints: readRequiredFiniteNumberValue(metadataRecord['effective_points'], 'Hardware history.metadata.effective_points'),
            maxPoints: readRequiredFiniteNumberValue(metadataRecord['max_points'], 'Hardware history.metadata.max_points'),
            bucketCount: readRequiredFiniteNumberValue(metadataRecord['bucket_count'], 'Hardware history.metadata.bucket_count'),
            bucketGapCount: readRequiredFiniteNumberValue(metadataRecord['bucket_gap_count'], 'Hardware history.metadata.bucket_gap_count'),
            loggingIntervalMs: readRequiredFiniteNumberValue(metadataRecord['logging_interval_ms'], 'Hardware history.metadata.logging_interval_ms'),
            monitoringIntervalMs: readRequiredFiniteNumberValue(metadataRecord['monitoring_interval_ms'], 'Hardware history.metadata.monitoring_interval_ms'),
            supportsOhlc: readRequiredBooleanValue(metadataRecord['supports_ohlc'], 'Hardware history.metadata.supports_ohlc'),
            retentionApplied: readRequiredBooleanValue(metadataRecord['retention_applied'], 'Hardware history.metadata.retention_applied'),
            retentionStartTsMs: readNullableFiniteNumberValue(metadataRecord['retention_start_ts_ms'], 'Hardware history.metadata.retention_start_ts_ms'),
            supportedIntervalsMs: decodeHardwareNumberArray(metadataRecord['supported_intervals_ms'], 'Hardware history.metadata.supported_intervals_ms') ?? [],
            component: readRequiredTrimmedStringValue(metadataRecord['component'], 'Hardware history.metadata.component'),
            deviceId: readNullableTrimmedStringValue(metadataRecord['device_id'], 'Hardware history.metadata.device_id'),
            identifier: readNullableTrimmedStringValue(metadataRecord['identifier'], 'Hardware history.metadata.identifier')
        }
    };
};

const decodeOptionalHardwareHistory = (value: ApiResponsePayload): HardwareHistoryResponse | null => {
    if (isJsonObject(value) && Object.keys(value).length === 0) return null;
    return decodeHardwareHistory(value);
};

const decodeKillProcessResponse = (value: ApiResponsePayload): KillProcessResponse => {
    const record = requireRecord(value, 'Kill process response');
    const status = readRequiredTrimmedStringValue(record['status'], 'Kill process response.status');
    readRequiredTrimmedStringValue(record['message'], 'Kill process response.message');
    return { status };
};
const decodeHardwareExportResponse = (value: ApiResponsePayload): Response => decodeRawResponse(value, 'Hardware history export response');

export { decodeGpuOperationResponse, decodeGpuSoAIBenchRun, decodeHardwareCapabilities, decodeHardwareExportResponse, decodeHardwareHistory, decodeHardwareSnapshot, decodeKillProcessResponse, decodeOptionalHardwareHistory, serializeGpuSoAIBenchRun };
export type { GpuIdentity, GpuOperationResponse, GpuSettingsUpdateRequest, GpuSlotStoreRequest, GpuSoAIBenchHistoryRun, GpuSoAIBenchRun, GpuSoAIBenchStartRequest, HardwareCapabilitiesResponse, HardwareGpuSnapshot, HardwareHistoryConfiguration, HardwareHistoryMetadata, HardwareHistoryResponse, HardwareMemorySnapshot, HardwareNetworkInterface, HardwareNetworkSpeed, HardwareSnapshotResponse, HardwareSummary, HardwareVolumeSnapshot, KillProcessResponse };
