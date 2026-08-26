/* SoAI - Frontend hardware API contract types [frontend/assets/ts/core/api/contracts/hardwareContractTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';
import type { GpuIdentity, GpuSoAIBenchHistoryRun, GpuSoAIBenchRun, GpuSoAIBenchStartRequest } from '@core/api/contracts/hardwareSoAIBenchTypes.ts';

interface HardwareHistoryConfiguration {
    enabled?: boolean | undefined;
    retentionHours?: number | undefined;
    loggingIntervalMs?: number | undefined;
    maxPoints?: number | undefined;
    supportedIntervalsMs?: number[] | undefined;
    supportedAggregations?: string[] | undefined;
    components?: string[] | undefined;
}
interface HardwareCapabilitiesResponse {
    platform?: string | undefined;
    historyConfig?: HardwareHistoryConfiguration | undefined;
    historyRetentionHours?: number | undefined;
    monitoringIntervalMs?: number | undefined;
    totalVramGb?: number | undefined;
    systemRamGb?: number | undefined;
    totalSystemMemoryGb?: number | undefined;
}
interface HardwareSummary {
    totalSystemRamGb?: number | undefined;
    totalVramGb?: number | undefined;
    totalSystemMemoryGb?: number | undefined;
}
interface HardwareMemorySnapshot {
    totalGb?: number | undefined;
    usedGb?: number | undefined;
    freeGb?: number | undefined;
    percentUsed?: number | undefined;
    percent?: number | undefined;
    totalBytes?: number | undefined;
    usedBytes?: number | undefined;
    freeBytes?: number | undefined;
}
interface HardwareUptimeSnapshot {
    uptimeMs?: number | undefined;
    bootTimeMs?: number | undefined;
}
interface HardwareOperatingSystemSnapshot {
    system?: string | undefined;
    nodeName?: string | undefined;
    release?: string | undefined;
    version?: string | undefined;
    machine?: string | undefined;
    processor?: string | undefined;
}
interface HardwareVolumeSnapshot {
    deviceId?: string | undefined;
    filesystem?: string | undefined;
    mount?: string | undefined;
    fstype?: string | undefined;
    totalBytes?: number | undefined;
    usedBytes?: number | undefined;
    freeBytes?: number | undefined;
    percentUsed?: number | undefined;
    storageBackend?: string | undefined;
    readOnly?: boolean | undefined;
    readOnlyReason?: string | null | undefined;
}
interface HardwareNetworkAddress {
    type?: string | undefined;
    address?: string | undefined;
    netmask?: string | undefined;
}
interface HardwareNetworkInterface {
    deviceId?: string | undefined;
    name?: string | undefined;
    macAddress?: string | undefined;
    addresses?: HardwareNetworkAddress[] | undefined;
    linkSpeedMbps?: number | undefined;
    isUp?: boolean | undefined;
}
interface HardwareNetworkSpeed {
    uploadMbps?: number | undefined;
    downloadMbps?: number | undefined;
    observedAtMs?: number | undefined;
}
interface HardwareCpuSnapshot {
    deviceId?: string | undefined;
    identifier?: string | undefined;
    index?: number | undefined;
    socketId?: number | string | undefined;
    name?: string | undefined;
    displayName?: string | undefined;
    model?: string | undefined;
    architecture?: string | undefined;
    physicalCores?: number | undefined;
    logicalCores?: number | undefined;
    usagePercent?: number | undefined;
    temperatureCelsius?: number | undefined;
    powerDrawWatts?: number | undefined;
    powerLimitWatts?: number | undefined;
}
interface HardwareGpuSnapshot {
    id?: number | undefined;
    deviceId?: string | undefined;
    index?: number | undefined;
    bindingIndex?: number | undefined;
    name?: string | undefined;
    displayName?: string | undefined;
    label?: string | undefined;
    vendor?: string | undefined;
    type?: string | undefined;
    displayAdapterType?: string | undefined;
    pciBdf?: string | undefined;
    gpuUuid?: string | undefined;
    kernelDriver?: string | undefined;
    telemetryUnavailableReason?: string | undefined;
    computeCapable?: boolean | undefined;
    telemetryAvailable?: boolean | undefined;
    utilization?: number | undefined;
    percentUsed?: number | undefined;
    temperature?: number | undefined;
    powerDrawWatts?: number | undefined;
    powerLimitWatts?: number | undefined;
    coreClockMhz?: number | undefined;
    memClockMhz?: number | undefined;
    memoryTotalBytes?: number | undefined;
    memoryUsedBytes?: number | undefined;
    memoryTotalMb?: number | undefined;
    memoryUsedMb?: number | undefined;
}
interface HardwareSnapshotResponse {
    timestampMs: number;
    summary: HardwareSummary;
    capabilities: HardwareCapabilitiesResponse;
    cpus?: HardwareCpuSnapshot[];
    cpu?: HardwareCpuSnapshot;
    memory?: HardwareMemorySnapshot | null;
    swap?: HardwareMemorySnapshot | null;
    uptime?: HardwareUptimeSnapshot;
    os?: HardwareOperatingSystemSnapshot;
    disk?: HardwareVolumeSnapshot[];
    gpu?: { gpus: HardwareGpuSnapshot[]; binding?: { devices: HardwareGpuSnapshot[] } };
    network?: { interfaces: HardwareNetworkInterface[]; byDeviceId?: Record<string, HardwareNetworkInterface> };
    networkSpeed?: Record<string, HardwareNetworkSpeed>;
    diskSpeed?: { status: string; observedAtMs?: number } | null;
}
interface HardwareHistoryMetadata {
    aggregation: string;
    intervalMs: number;
    requestedIntervalMs: number | null;
    intervalSource: string;
    startTsMs: number;
    requestedStartTsMs: number;
    endTsMs: number;
    requestedEndTsMs: number;
    alignedStartTsMs: number;
    alignedEndTsMs: number;
    durationMs: number;
    requestedDurationMs: number;
    points: number;
    requestedPoints: number;
    effectivePoints: number;
    maxPoints: number;
    bucketCount: number;
    bucketGapCount: number;
    loggingIntervalMs: number;
    monitoringIntervalMs: number;
    supportsOhlc: boolean;
    retentionApplied: boolean;
    retentionStartTsMs: number | null;
    supportedIntervalsMs: number[];
    component: string;
    deviceId: string | null;
    identifier: string | null;
}
interface HardwareHistoryResponse {
    aggregation: string;
    intervalMs: number;
    timestampsMs: number[];
    metrics: string[];
    data: JsonObject[];
    metadata: HardwareHistoryMetadata;
}
interface HardwareHistoryRequest {
    component: string;
    aggregation?: string | undefined;
    points: number;
    startTsMs: number;
    endTsMs: number;
    gpuIndex?: number | undefined;
    identifier?: string | undefined;
    intervalMs?: number | undefined;
}
type GpuSettingValue = number | 'auto' | null;
interface GpuSettingsUpdateRequest {
    powerLimit?: GpuSettingValue;
    coreClock?: GpuSettingValue;
    memClock?: GpuSettingValue;
    fanSpeed?: GpuSettingValue;
    resetClocks?: boolean;
}
interface GpuSlotStoreRequest {
    settings: GpuSettingsUpdateRequest;
    fieldModes?: Partial<Record<'powerLimit' | 'coreClock' | 'memClock' | 'fanSpeed', 'auto' | 'manual'>>;
}
interface GpuOperationResponse {
    success?: boolean | undefined;
    code?: string | undefined;
    accepted?: boolean | undefined;
    status?: string | undefined;
    failureReason?: string | undefined;
    unsupportedReason?: string | undefined;
    slotState?: { settings?: GpuSettingsUpdateRequest | undefined; fieldModes?: GpuSlotStoreRequest['fieldModes'] | undefined };
    boot?: { enabled?: boolean | undefined; slot?: string | undefined };
    runId?: string | undefined;
    profile?: string | undefined;
    active?: boolean | undefined;
    runs?: GpuSoAIBenchRun[] | undefined;
    history?: GpuSoAIBenchHistoryRun[] | undefined;
}
interface KillProcessResponse {
    status: string;
}

export type { GpuIdentity, GpuOperationResponse, GpuSettingValue, GpuSettingsUpdateRequest, GpuSlotStoreRequest, GpuSoAIBenchHistoryRun, GpuSoAIBenchRun, GpuSoAIBenchStartRequest, HardwareCapabilitiesResponse, HardwareCpuSnapshot, HardwareGpuSnapshot, HardwareHistoryConfiguration, HardwareHistoryMetadata, HardwareHistoryRequest, HardwareHistoryResponse, HardwareMemorySnapshot, HardwareNetworkAddress, HardwareNetworkInterface, HardwareNetworkSpeed, HardwareOperatingSystemSnapshot, HardwareSnapshotResponse, HardwareSummary, HardwareUptimeSnapshot, HardwareVolumeSnapshot, KillProcessResponse };
