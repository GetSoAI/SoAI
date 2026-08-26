/* SoAI - Hardware snapshot GPU V1 boundary decoding [frontend/assets/ts/core/api/contracts/hardwareSnapshotGpuContract.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readOptionalHardwareNumber, readOptionalHardwareString } from '@core/api/contracts/hardwareContractReaders.ts';
import type { HardwareGpuSnapshot } from '@core/api/contracts/hardwareContractTypes.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

const decodeHardwareSnapshotGpu = (record: JsonObject, label: string): HardwareGpuSnapshot => {
    const decoded: HardwareGpuSnapshot = {};
    const deviceId = readOptionalHardwareString(record, 'device_id', label);
    const name = readOptionalHardwareString(record, 'name', label);
    const displayName = readOptionalHardwareString(record, 'display_name', label);
    const displayLabel = readOptionalHardwareString(record, 'label', label);
    const vendor = readOptionalHardwareString(record, 'vendor', label);
    const type = readOptionalHardwareString(record, 'type', label);
    const displayAdapterType = readOptionalHardwareString(record, 'display_adapter_type', label);
    const pciBdf = readOptionalHardwareString(record, 'pci_bdf', label);
    const gpuUuid = readOptionalHardwareString(record, 'gpu_uuid', label);
    const kernelDriver = readOptionalHardwareString(record, 'kernel_driver', label);
    const telemetryUnavailableReason = readOptionalHardwareString(record, 'telemetry_unavailable_reason', label);
    const id = readOptionalHardwareNumber(record, 'id', label);
    const index = readOptionalHardwareNumber(record, 'index', label);
    const bindingIndex = readOptionalHardwareNumber(record, 'binding_index', label);
    const utilization = readOptionalHardwareNumber(record, 'utilization', label);
    const percentUsed = readOptionalHardwareNumber(record, 'percent_used', label);
    const temperature = readOptionalHardwareNumber(record, 'temperature', label);
    const powerDrawWatts = readOptionalHardwareNumber(record, 'power_draw_watts', label);
    const powerLimitWatts = readOptionalHardwareNumber(record, 'power_limit_watts', label);
    const coreClockMhz = readOptionalHardwareNumber(record, 'core_clock_mhz', label);
    const memClockMhz = readOptionalHardwareNumber(record, 'mem_clock_mhz', label);
    const memoryTotalBytes = readOptionalHardwareNumber(record, 'memory_total_bytes', label);
    const memoryUsedBytes = readOptionalHardwareNumber(record, 'memory_used_bytes', label);
    const memoryTotalMb = readOptionalHardwareNumber(record, 'memory_total_mb', label);
    const memoryUsedMb = readOptionalHardwareNumber(record, 'memory_used_mb', label);
    if (deviceId !== undefined) decoded.deviceId = deviceId;
    if (name !== undefined) decoded.name = name;
    if (displayName !== undefined) decoded.displayName = displayName;
    if (displayLabel !== undefined) decoded.label = displayLabel;
    if (vendor !== undefined) decoded.vendor = vendor;
    if (type !== undefined) decoded.type = type;
    if (displayAdapterType !== undefined) decoded.displayAdapterType = displayAdapterType;
    if (pciBdf !== undefined) decoded.pciBdf = pciBdf;
    if (gpuUuid !== undefined) decoded.gpuUuid = gpuUuid;
    if (kernelDriver !== undefined) decoded.kernelDriver = kernelDriver;
    if (telemetryUnavailableReason !== undefined) decoded.telemetryUnavailableReason = telemetryUnavailableReason;
    if (id !== undefined) decoded.id = id;
    if (index !== undefined) decoded.index = index;
    if (bindingIndex !== undefined) decoded.bindingIndex = bindingIndex;
    if (utilization !== undefined) decoded.utilization = utilization;
    if (percentUsed !== undefined) decoded.percentUsed = percentUsed;
    if (temperature !== undefined) decoded.temperature = temperature;
    if (powerDrawWatts !== undefined) decoded.powerDrawWatts = powerDrawWatts;
    if (powerLimitWatts !== undefined) decoded.powerLimitWatts = powerLimitWatts;
    if (coreClockMhz !== undefined) decoded.coreClockMhz = coreClockMhz;
    if (memClockMhz !== undefined) decoded.memClockMhz = memClockMhz;
    if (memoryTotalBytes !== undefined) decoded.memoryTotalBytes = memoryTotalBytes;
    if (memoryUsedBytes !== undefined) decoded.memoryUsedBytes = memoryUsedBytes;
    if (memoryTotalMb !== undefined) decoded.memoryTotalMb = memoryTotalMb;
    if (memoryUsedMb !== undefined) decoded.memoryUsedMb = memoryUsedMb;
    if (typeof record['compute_capable'] === 'boolean') decoded.computeCapable = record['compute_capable'];
    if (typeof record['telemetry_available'] === 'boolean') decoded.telemetryAvailable = record['telemetry_available'];
    return decoded;
};

export { decodeHardwareSnapshotGpu };
