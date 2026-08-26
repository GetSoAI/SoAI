/* SoAI - Hardware widget domain contracts [frontend/assets/ts/features/hardware/widgets/internalContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { HardwareHistoryResponse, HardwareGpuSnapshot } from '@core/api/contracts/hardwareContracts.ts';
import type { CpuRaw, HardwareSnapshot, MemoryRaw, NetworkInterfaceRaw } from '@features/hardware/models/types.ts';

type CPURawData = CpuRaw;
type GPURawData = HardwareGpuSnapshot;
type NetworkRawData = NetworkInterfaceRaw;
type MemoryData = MemoryRaw;
type HardwareData = HardwareSnapshot;

interface CPUDeviceData {
    utilization: number;
    memoryUsedMb: number;
    memoryTotalMb: number;
    temperature: number;
    powerWatts: number;
    powerLimit: number;
}
interface GPUDeviceData {
    utilization: number;
    memoryUsedMb: number;
    memoryTotalMb: number;
    powerWatts: number;
    temperature: number;
    powerLimit: number;
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
    index: number;
    name: string;
    data: GPUDeviceData;
}
interface NetworkDeviceData {
    downloadMbps: number;
    uploadMbps: number;
    linkSpeedMbps: number;
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
