/* SoAI - Frontend hardware domain model contracts [frontend/assets/ts/features/hardware/models/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { HardwareCapabilitiesResponse, HardwareGpuSnapshot } from '@core/api/contracts/hardwareContracts.ts';

interface NetworkSpeedEntry {
    downloadMbps?: number | undefined;
    uploadMbps?: number | undefined;
    observedAtMs?: number | undefined;
}
type NetworkSpeedSnapshot = Record<string, NetworkSpeedEntry>;

interface VolumeRaw {
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
interface VolumeModel {
    deviceId: string;
    filesystem: string;
    mount: string;
    fstype: string;
    size: string;
    used: string;
    available: string;
    percentUsed: number;
    sizeGb: number;
    totalBytes: number;
    usedBytes: number;
    freeBytes: number;
    storageBackend: string;
    readOnly: boolean;
    readOnlyReason: string | null;
}
interface VolumeOptions {
    ignoredFilesystems?: readonly string[] | undefined;
    ignoredMounts?: readonly string[] | undefined;
    minCapacityGb?: number | undefined;
}

interface NetworkAddress {
    type?: string | undefined;
    address?: string | undefined;
    netmask?: string | undefined;
}
interface NetworkInterfaceRaw {
    deviceId?: string | undefined;
    name?: string | undefined;
    macAddress?: string | undefined;
    addresses?: NetworkAddress[] | undefined;
    linkSpeedMbps?: number | undefined;
    isUp?: boolean | undefined;
}
interface NetworkInterfaceModel {
    name: string;
    deviceId: string;
    addresses: NetworkAddress[];
    primaryAddr: NetworkAddress | null;
    secondaryAddr: NetworkAddress | null;
    mac: string | null;
    dlMbps: number;
    ulMbps: number;
    observedAtMs: number;
    linkSpeedMbps: number;
    isUp: boolean | null;
}
interface NetworkInterfaceOptions {
    ignorePrefixes?: readonly string[] | undefined;
}
interface NetworkModelOptions {
    speeds?: NetworkSpeedSnapshot | undefined;
    ignorePrefixes?: readonly string[] | undefined;
}

interface CpuRaw {
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
interface MemoryRaw {
    totalGb?: number | undefined;
    usedGb?: number | undefined;
    freeGb?: number | undefined;
    percentUsed?: number | undefined;
    percent?: number | undefined;
    totalBytes?: number | undefined;
    usedBytes?: number | undefined;
    freeBytes?: number | undefined;
}
interface HardwareSnapshot {
    timestampMs?: number | undefined;
    summary?: { totalSystemRamGb?: number | undefined; totalVramGb?: number | undefined; totalSystemMemoryGb?: number | undefined } | undefined;
    capabilities?: HardwareCapabilitiesResponse | undefined;
    disk?: VolumeRaw[] | undefined;
    cpus?: CpuRaw[] | undefined;
    cpu?: CpuRaw | undefined;
    memory?: MemoryRaw | null | undefined;
    swap?: MemoryRaw | null | undefined;
    uptime?: { uptimeMs?: number | undefined; bootTimeMs?: number | undefined } | undefined;
    gpu?: { gpus?: HardwareGpuSnapshot[] | undefined } | undefined;
    network?: { interfaces?: NetworkInterfaceRaw[] | undefined; byDeviceId?: Record<string, NetworkInterfaceRaw> | undefined } | undefined;
    networkSpeed?: NetworkSpeedSnapshot | undefined;
}

type GPURaw = HardwareGpuSnapshot;
interface HardwareModelsOptions {
    volumes?: VolumeOptions | undefined;
    network?: NetworkModelOptions | undefined;
}
interface HardwareModels {
    cpus: CpuRaw[];
    gpus: HardwareGpuSnapshot[];
    volumes: VolumeModel[];
    networkInterfaces: NetworkInterfaceModel[];
}

export type { CpuRaw, GPURaw, HardwareModels, HardwareModelsOptions, HardwareSnapshot, MemoryRaw, NetworkAddress, NetworkInterfaceModel, NetworkInterfaceOptions, NetworkInterfaceRaw, NetworkModelOptions, NetworkSpeedEntry, NetworkSpeedSnapshot, VolumeModel, VolumeOptions, VolumeRaw };
