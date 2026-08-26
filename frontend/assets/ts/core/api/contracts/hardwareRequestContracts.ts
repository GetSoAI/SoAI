/* SoAI - Frontend hardware outbound request boundary contracts [frontend/assets/ts/core/api/contracts/hardwareRequestContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GpuSettingsUpdateRequest, GpuSlotStoreRequest, GpuSoAIBenchStartRequest, HardwareHistoryRequest } from '@core/api/contracts/hardwareContractTypes.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

const serializeGpuSettingsUpdateRequest = (request: GpuSettingsUpdateRequest): JsonObject => {
    const serialized: JsonObject = {};
    if (request.powerLimit !== undefined) serialized['power_limit'] = request.powerLimit;
    if (request.coreClock !== undefined) serialized['core_clock'] = request.coreClock;
    if (request.memClock !== undefined) serialized['mem_clock'] = request.memClock;
    if (request.fanSpeed !== undefined) serialized['fan_speed'] = request.fanSpeed;
    if (request.resetClocks !== undefined) serialized['reset_clocks'] = request.resetClocks;
    return serialized;
};

const serializeGpuFieldModes = (fieldModes: NonNullable<GpuSlotStoreRequest['fieldModes']>): JsonObject => {
    const serialized: JsonObject = {};
    if (fieldModes.powerLimit !== undefined) serialized['power_limit'] = fieldModes.powerLimit;
    if (fieldModes.coreClock !== undefined) serialized['core_clock'] = fieldModes.coreClock;
    if (fieldModes.memClock !== undefined) serialized['mem_clock'] = fieldModes.memClock;
    if (fieldModes.fanSpeed !== undefined) serialized['fan_speed'] = fieldModes.fanSpeed;
    return serialized;
};

const serializeGpuSoAIBenchStartRequest = (request: GpuSoAIBenchStartRequest): JsonObject => {
    const serialized: JsonObject = { profile: request.profile };
    if (request.benchmarkMode !== undefined) serialized['benchmark_mode'] = request.benchmarkMode;
    if (request.temperatureLimitCelsius !== undefined) serialized['temperature_limit_celsius'] = request.temperatureLimitCelsius;
    return serialized;
};

const serializeGpuDeviceSettingsRequest = (deviceId: string, request: GpuSettingsUpdateRequest): JsonObject => ({ 'device_id': deviceId, ...serializeGpuSettingsUpdateRequest(request) });

const serializeGpuSoAIBenchDeviceStartRequest = (deviceId: string, request: GpuSoAIBenchStartRequest): JsonObject => ({ 'device_id': deviceId, ...serializeGpuSoAIBenchStartRequest(request) });

const serializeGpuDeviceRequest = (deviceId: string): JsonObject => ({ 'device_id': deviceId });
const serializeGpuSlotBootRequest = (deviceId: string, enabled: boolean): JsonObject => ({ 'device_id': deviceId, enabled });

const serializeGpuSlotStoreRequest = (deviceId: string, request: GpuSlotStoreRequest, applyAtBoot: boolean | undefined): JsonObject => {
    const serialized: JsonObject = { 'device_id': deviceId, settings: serializeGpuSettingsUpdateRequest(request.settings) };
    if (request.fieldModes !== undefined) serialized['field_modes'] = serializeGpuFieldModes(request.fieldModes);
    if (applyAtBoot !== undefined) serialized['apply_at_boot'] = applyAtBoot;
    return serialized;
};

const serializeGpuSlotApplyDeviceRequest = (deviceId: string, applyAtBoot: boolean | undefined): JsonObject => {
    const serialized: JsonObject = { 'device_id': deviceId };
    if (applyAtBoot !== undefined) serialized['apply_at_boot'] = applyAtBoot;
    return serialized;
};

const serializeGpuRunIdentifierRequest = (runId: string): JsonObject => ({ 'run_id': runId });

const serializeGpuSoAIBenchHistoryRequest = (deviceId: string, historyLimit: number): JsonObject => ({ 'device_id': deviceId, 'history_limit': historyLimit });

const serializeGpuSlotApplyRequest = (deviceId: string, slot: string, applyAtBoot: boolean | undefined): JsonObject => {
    const serialized: JsonObject = { 'device_id': deviceId, slot };
    if (applyAtBoot !== undefined) serialized['apply_at_boot'] = applyAtBoot;
    return serialized;
};

const serializeGpuSlotStoreSnapshotRequest = (deviceId: string, slot: string, request: GpuSlotStoreRequest): JsonObject => {
    const serialized: JsonObject = { 'device_id': deviceId, slot, settings: serializeGpuSettingsUpdateRequest(request.settings) };
    if (request.fieldModes !== undefined) {
        serialized['field_modes'] = serializeGpuFieldModes(request.fieldModes);
    }
    return serialized;
};

const serializeKillProcessRequest = (processId: number, signal: number, useSudo: boolean): JsonObject => ({ pid: processId, signal, 'use_sudo': useSudo });
const serializeKillProcessRestRequest = (signal: number, useSudo: boolean): JsonObject => ({ signal, 'use_sudo': useSudo });

const serializeHardwareHistoryRequest = (request: HardwareHistoryRequest): JsonObject => {
    const serialized: JsonObject = { component: request.component, points: request.points, 'start_ts_ms': request.startTsMs, 'end_ts_ms': request.endTsMs };
    if (request.aggregation !== undefined) serialized['aggregation'] = request.aggregation;
    if (request.gpuIndex !== undefined) serialized['gpu_index'] = request.gpuIndex;
    if (request.identifier !== undefined) serialized['identifier'] = request.identifier;
    if (request.intervalMs !== undefined) serialized['interval_ms'] = request.intervalMs;
    return serialized;
};

const serializeHardwareExportRequest = (request: Pick<HardwareHistoryRequest, 'component' | 'gpuIndex' | 'identifier'>): JsonObject => {
    const serialized: JsonObject = { component: request.component };
    if (request.gpuIndex !== undefined) serialized['gpu_index'] = request.gpuIndex;
    if (request.identifier !== undefined) serialized['identifier'] = request.identifier;
    return serialized;
};

export { serializeGpuDeviceRequest, serializeGpuDeviceSettingsRequest, serializeGpuFieldModes, serializeGpuRunIdentifierRequest, serializeGpuSettingsUpdateRequest, serializeGpuSlotApplyDeviceRequest, serializeGpuSlotApplyRequest, serializeGpuSlotBootRequest, serializeGpuSlotStoreRequest, serializeGpuSlotStoreSnapshotRequest, serializeGpuSoAIBenchDeviceStartRequest, serializeGpuSoAIBenchHistoryRequest, serializeGpuSoAIBenchStartRequest, serializeHardwareExportRequest, serializeHardwareHistoryRequest, serializeKillProcessRequest, serializeKillProcessRestRequest };
