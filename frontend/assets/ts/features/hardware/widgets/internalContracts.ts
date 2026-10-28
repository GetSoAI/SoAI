/* SoAI - Hardware widget domain contracts [frontend/assets/ts/features/hardware/widgets/internalContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { HardwareCpuSnapshot, HardwareMemorySnapshot, HardwareNetworkInterface } from '@core/api/contracts/hardwareContractTypes.ts';
import type { HardwareHistoryResponse, HardwareGpuSnapshot } from '@core/api/contracts/hardwareContracts.ts';
import type { HardwareSnapshot } from '@features/hardware/models/types.ts';
import type { HardwareComponentObservation } from '@core/api/contracts/hardwareComponentObservationContracts.ts';

type CPURawData = HardwareCpuSnapshot;
type GPURawData = HardwareGpuSnapshot;
type NetworkRawData = HardwareNetworkInterface;
type MemoryData = HardwareMemorySnapshot;
type HardwareData = HardwareSnapshot;

interface CPUDeviceData {
    utilization?: number | undefined;
    memoryUsedMb?: number | undefined;
    memoryTotalMb?: number | undefined;
    temperature?: number | undefined;
    powerWatts?: number | undefined;
    powerLimit?: number | undefined;
}
interface GPUDeviceData {
    telemetryObservation?: HardwareComponentObservation | undefined;
    memoryTotalObservation?: HardwareComponentObservation | undefined;
    utilization?: number | undefined;
    memoryUsedMb?: number | undefined;
    memoryTotalMb?: number | undefined;
    powerWatts?: number | undefined;
    temperature?: number | undefined;
    powerLimit?: number | undefined;
    telemetryAvailable: boolean;
}
interface CPUDevice {
    socketIndex: number;
    name: string;
    sockets: number;
    cores: number;
    threads: number;
    data: CPUDeviceData;
}
interface GPUDevice {
    deviceId?: string | undefined;
    index: number;
    name: string;
    data: GPUDeviceData;
}
interface NetworkDeviceData {
    downloadMbps?: number | undefined;
    uploadMbps?: number | undefined;
    linkSpeedMbps?: number | undefined;
}
interface NetworkDevice {
    deviceId: string;
    index: number;
    name: string;
    data: NetworkDeviceData;
}
type HistoryResponse = HardwareHistoryResponse;
interface WidgetHistoryWindow {
    durationMs: number;
    points: number;
    requestPaddingMs: number;
}
interface WidgetHistoryRequest {
    component: string;
    gpuIndex: number | null;
    identifier?: string | undefined;
    startTsMs: number;
    endTsMs: number;
    points: number;
    signal: AbortSignal;
}
interface HardwareApi {
    history: (config: { component: string; startTsMs: number; endTsMs: number; points: number; options: { signal: AbortSignal }; gpuIndex?: number | undefined; identifier?: string | undefined }) => Promise<HardwareHistoryResponse | null>;
}
type HardwareSnapshotInput = HardwareSnapshot;

export { type CPURawData, type GPURawData, type NetworkRawData, type MemoryData, type HardwareSnapshot, type HardwareData, type CPUDeviceData, type GPUDeviceData, type NetworkDeviceData, type CPUDevice, type GPUDevice, type NetworkDevice, type HistoryResponse, type WidgetHistoryWindow, type WidgetHistoryRequest, type HardwareApi, type HardwareSnapshotInput };
