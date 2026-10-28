/* SoAI - Frontend hardware domain model contracts [frontend/assets/ts/features/hardware/models/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { HardwareCpuSnapshot, HardwareGpuSnapshot, HardwareMemorySnapshot, HardwareNetworkAddress, HardwareNetworkInterface, HardwareNetworkSpeed, HardwareVolumeSnapshot, HardwareSummary, HardwareUptimeSnapshot } from '@core/api/contracts/hardwareContractTypes.ts';
import type { HardwareComponentObservation } from '@core/api/contracts/hardwareComponentObservationContracts.ts';
import type { HardwareCapabilitiesResponse, WindowsNetworkInventoryStatus } from '@core/api/contracts/hardwareContracts.ts';

type NetworkSpeedSnapshot = Record<string, HardwareNetworkSpeed>;

interface VolumeModel {
    observationStatus?: HardwareComponentObservation | undefined;
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

interface NetworkInterfaceModel {
    observationStatus?: HardwareComponentObservation | undefined;
    name: string;
    deviceId: string;
    addresses: HardwareNetworkAddress[];
    primaryAddr: HardwareNetworkAddress | null;
    secondaryAddr: HardwareNetworkAddress | null;
    mac: string | null;
    dlMbps?: number | undefined;
    ulMbps?: number | undefined;
    observedAtMs: number;
    linkSpeedMbps: number;
    isUp: boolean | null;
}
interface NetworkInterfaceOptions {
    ignorePrefixes?: readonly string[] | undefined;
    windowsInventoryStatus?: WindowsNetworkInventoryStatus | null | undefined;
}
interface NetworkModelOptions {
    speeds?: NetworkSpeedSnapshot | undefined;
    ignorePrefixes?: readonly string[] | undefined;
}

interface HardwareSnapshot {
    componentStatus?: Record<string, HardwareComponentObservation> | undefined;
    timestampMs?: number | undefined;
    summary?: HardwareSummary | undefined;
    capabilities?: HardwareCapabilitiesResponse | undefined;
    disk?: HardwareVolumeSnapshot[] | undefined;
    cpus?: HardwareCpuSnapshot[] | undefined;
    cpu?: HardwareCpuSnapshot | undefined;
    memory?: HardwareMemorySnapshot | null | undefined;
    swap?: HardwareMemorySnapshot | null | undefined;
    uptime?: HardwareUptimeSnapshot | undefined;
    gpu?: { gpus?: HardwareGpuSnapshot[] | undefined } | undefined;
    network?: { interfaces?: HardwareNetworkInterface[] | undefined; byDeviceId?: Record<string, HardwareNetworkInterface> | undefined; windowsInventoryStatus?: WindowsNetworkInventoryStatus | undefined } | undefined;
    networkSpeed?: NetworkSpeedSnapshot | undefined;
}

interface HardwareModelsOptions {
    volumes?: VolumeOptions | undefined;
    network?: NetworkModelOptions | undefined;
}
interface HardwareModels {
    cpus: HardwareCpuSnapshot[];
    gpus: HardwareGpuSnapshot[];
    volumes: VolumeModel[];
    networkInterfaces: NetworkInterfaceModel[];
}

export type { HardwareModels, HardwareModelsOptions, HardwareSnapshot, NetworkInterfaceModel, NetworkInterfaceOptions, NetworkModelOptions, NetworkSpeedSnapshot, VolumeModel, VolumeOptions };
