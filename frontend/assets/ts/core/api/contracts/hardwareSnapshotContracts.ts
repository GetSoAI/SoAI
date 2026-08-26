/* SoAI - Hardware snapshot V1 boundary decoding [frontend/assets/ts/core/api/contracts/hardwareSnapshotContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { decodeHardwareNumberArray, decodeHardwareStringArray, readOptionalHardwareNumber, readOptionalHardwareString } from '@core/api/contracts/hardwareContractReaders.ts';
import { decodeHardwareSnapshotGpu } from '@core/api/contracts/hardwareSnapshotGpuContract.ts';
import { decodeHardwareOperatingSystemSnapshot } from '@core/api/contracts/hardwareSnapshotSystemContract.ts';
import { isEpochMsNumber } from '@core/time/epochMs.ts';
import { readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableTrimmedStringValue, readRequiredBooleanValue } from '@core/types/payloadValueReaders.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { HardwareCapabilitiesResponse, HardwareCpuSnapshot, HardwareHistoryConfiguration, HardwareMemorySnapshot, HardwareNetworkAddress, HardwareNetworkInterface, HardwareNetworkSpeed, HardwareSnapshotResponse, HardwareSummary, HardwareUptimeSnapshot, HardwareVolumeSnapshot } from '@core/api/contracts/hardwareContractTypes.ts';

const decodeHardwareHistoryConfiguration = (value: JsonValue | undefined): HardwareHistoryConfiguration | undefined => {
    if (value === undefined || value === null) return undefined;
    const record = requireRecord(value, 'Hardware capabilities.history_config');
    const decoded: HardwareHistoryConfiguration = {};
    if (record['enabled'] !== undefined) decoded.enabled = readRequiredBooleanValue(record['enabled'], 'Hardware capabilities.history_config.enabled');
    const retentionHours = readOptionalHardwareNumber(record, 'retention_hours', 'Hardware capabilities.history_config');
    const loggingIntervalMs = readOptionalHardwareNumber(record, 'logging_interval_ms', 'Hardware capabilities.history_config');
    const maxPoints = readOptionalHardwareNumber(record, 'max_points', 'Hardware capabilities.history_config');
    const supportedIntervalsMs = decodeHardwareNumberArray(record['supported_intervals_ms'], 'Hardware capabilities.history_config.supported_intervals_ms');
    const supportedAggregations = decodeHardwareStringArray(record['supported_aggregations'], 'Hardware capabilities.history_config.supported_aggregations');
    const components = decodeHardwareStringArray(record['components'], 'Hardware capabilities.history_config.components');
    if (retentionHours !== undefined) decoded.retentionHours = retentionHours;
    if (loggingIntervalMs !== undefined) decoded.loggingIntervalMs = loggingIntervalMs;
    if (maxPoints !== undefined) decoded.maxPoints = maxPoints;
    if (supportedIntervalsMs !== undefined) decoded.supportedIntervalsMs = supportedIntervalsMs;
    if (supportedAggregations !== undefined) decoded.supportedAggregations = supportedAggregations;
    if (components !== undefined) decoded.components = components;
    return decoded;
};

const decodeHardwareCapabilities = (value: ApiResponsePayload | JsonValue): HardwareCapabilitiesResponse => {
    const record = requireRecord(value, 'Hardware capabilities');
    const decoded: HardwareCapabilitiesResponse = {};
    const platform = readOptionalHardwareString(record, 'platform', 'Hardware capabilities');
    const historyConfig = decodeHardwareHistoryConfiguration(record['history_config']);
    const historyRetentionHours = readOptionalHardwareNumber(record, 'history_retention_hours', 'Hardware capabilities');
    const monitoringIntervalMs = readOptionalHardwareNumber(record, 'monitoring_interval_ms', 'Hardware capabilities');
    const totalVramGb = readOptionalHardwareNumber(record, 'total_vram_gb', 'Hardware capabilities');
    const systemRamGb = readOptionalHardwareNumber(record, 'system_ram_gb', 'Hardware capabilities');
    const totalSystemMemoryGb = readOptionalHardwareNumber(record, 'total_system_memory_gb', 'Hardware capabilities');
    if (platform !== undefined) decoded.platform = platform;
    if (historyConfig !== undefined) decoded.historyConfig = historyConfig;
    if (historyRetentionHours !== undefined) decoded.historyRetentionHours = historyRetentionHours;
    if (monitoringIntervalMs !== undefined) decoded.monitoringIntervalMs = monitoringIntervalMs;
    if (totalVramGb !== undefined) decoded.totalVramGb = totalVramGb;
    if (systemRamGb !== undefined) decoded.systemRamGb = systemRamGb;
    if (totalSystemMemoryGb !== undefined) decoded.totalSystemMemoryGb = totalSystemMemoryGb;
    return decoded;
};

const decodeSummary = (record: JsonObject): HardwareSummary => {
    const decoded: HardwareSummary = {};
    const totalSystemRamGb = readOptionalHardwareNumber(record, 'total_system_ram_gb', 'Hardware snapshot.summary');
    const totalVramGb = readOptionalHardwareNumber(record, 'total_vram_gb', 'Hardware snapshot.summary');
    const totalSystemMemoryGb = readOptionalHardwareNumber(record, 'total_system_memory_gb', 'Hardware snapshot.summary');
    if (totalSystemRamGb !== undefined) decoded.totalSystemRamGb = totalSystemRamGb;
    if (totalVramGb !== undefined) decoded.totalVramGb = totalVramGb;
    if (totalSystemMemoryGb !== undefined) decoded.totalSystemMemoryGb = totalSystemMemoryGb;
    return decoded;
};

const decodeCpu = (value: JsonValue, label: string): HardwareCpuSnapshot => {
    const record = requireRecord(value, label);
    const socketIdValue = record['socket_id'];
    const socketId = typeof socketIdValue === 'string' ? socketIdValue : readOptionalHardwareNumber(record, 'socket_id', label);
    const decoded: HardwareCpuSnapshot = {};
    const fields = {
        deviceId: readOptionalHardwareString(record, 'device_id', label),
        identifier: readOptionalHardwareString(record, 'identifier', label),
        index: readOptionalHardwareNumber(record, 'index', label),
        socketId,
        name: readOptionalHardwareString(record, 'name', label),
        displayName: readOptionalHardwareString(record, 'display_name', label),
        model: readOptionalHardwareString(record, 'model', label),
        architecture: readOptionalHardwareString(record, 'architecture', label),
        physicalCores: readOptionalHardwareNumber(record, 'physical_cores', label),
        logicalCores: readOptionalHardwareNumber(record, 'logical_cores', label),
        usagePercent: readOptionalHardwareNumber(record, 'usage_percent', label),
        temperatureCelsius: readOptionalHardwareNumber(record, 'temperature_celsius', label),
        powerDrawWatts: readOptionalHardwareNumber(record, 'power_draw_watts', label),
        powerLimitWatts: readOptionalHardwareNumber(record, 'power_limit_watts', label)
    };
    if (fields.deviceId !== undefined) decoded.deviceId = fields.deviceId;
    if (fields.identifier !== undefined) decoded.identifier = fields.identifier;
    if (fields.index !== undefined) decoded.index = fields.index;
    if (fields.socketId !== undefined) decoded.socketId = fields.socketId;
    if (fields.name !== undefined) decoded.name = fields.name;
    if (fields.displayName !== undefined) decoded.displayName = fields.displayName;
    if (fields.model !== undefined) decoded.model = fields.model;
    if (fields.architecture !== undefined) decoded.architecture = fields.architecture;
    if (fields.physicalCores !== undefined) decoded.physicalCores = fields.physicalCores;
    if (fields.logicalCores !== undefined) decoded.logicalCores = fields.logicalCores;
    if (fields.usagePercent !== undefined) decoded.usagePercent = fields.usagePercent;
    if (fields.temperatureCelsius !== undefined) decoded.temperatureCelsius = fields.temperatureCelsius;
    if (fields.powerDrawWatts !== undefined) decoded.powerDrawWatts = fields.powerDrawWatts;
    if (fields.powerLimitWatts !== undefined) decoded.powerLimitWatts = fields.powerLimitWatts;
    return decoded;
};

const decodeMemory = (record: JsonObject, label: string): HardwareMemorySnapshot => {
    const decoded: HardwareMemorySnapshot = {};
    const fields = {
        totalGb: readOptionalHardwareNumber(record, 'total_gb', label),
        usedGb: readOptionalHardwareNumber(record, 'used_gb', label),
        freeGb: readOptionalHardwareNumber(record, 'free_gb', label),
        percentUsed: readOptionalHardwareNumber(record, 'percent_used', label),
        percent: readOptionalHardwareNumber(record, 'percent', label),
        totalBytes: readOptionalHardwareNumber(record, 'total_bytes', label),
        usedBytes: readOptionalHardwareNumber(record, 'used_bytes', label),
        freeBytes: readOptionalHardwareNumber(record, 'free_bytes', label)
    };
    if (fields.totalGb !== undefined) decoded.totalGb = fields.totalGb;
    if (fields.usedGb !== undefined) decoded.usedGb = fields.usedGb;
    if (fields.freeGb !== undefined) decoded.freeGb = fields.freeGb;
    if (fields.percentUsed !== undefined) decoded.percentUsed = fields.percentUsed;
    if (fields.percent !== undefined) decoded.percent = fields.percent;
    if (fields.totalBytes !== undefined) decoded.totalBytes = fields.totalBytes;
    if (fields.usedBytes !== undefined) decoded.usedBytes = fields.usedBytes;
    if (fields.freeBytes !== undefined) decoded.freeBytes = fields.freeBytes;
    return decoded;
};

const decodeVolume = (record: JsonObject): HardwareVolumeSnapshot => {
    const decoded: HardwareVolumeSnapshot = {};
    const label = 'Hardware volume';
    const deviceId = readOptionalHardwareString(record, 'device_id', label);
    const filesystem = readOptionalHardwareString(record, 'filesystem', label);
    const mount = readOptionalHardwareString(record, 'mount', label);
    const filesystemType = readOptionalHardwareString(record, 'fstype', label);
    const totalBytes = readOptionalHardwareNumber(record, 'total_bytes', label);
    const usedBytes = readOptionalHardwareNumber(record, 'used_bytes', label);
    const freeBytes = readOptionalHardwareNumber(record, 'free_bytes', label);
    const percentUsed = readOptionalHardwareNumber(record, 'percent_used', label);
    const storageBackend = readOptionalHardwareString(record, 'storage_backend', label);
    if (deviceId !== undefined) decoded.deviceId = deviceId;
    if (filesystem !== undefined) decoded.filesystem = filesystem;
    if (mount !== undefined) decoded.mount = mount;
    if (filesystemType !== undefined) decoded.fstype = filesystemType;
    if (totalBytes !== undefined) decoded.totalBytes = totalBytes;
    if (usedBytes !== undefined) decoded.usedBytes = usedBytes;
    if (freeBytes !== undefined) decoded.freeBytes = freeBytes;
    if (percentUsed !== undefined) decoded.percentUsed = percentUsed;
    if (storageBackend !== undefined) decoded.storageBackend = storageBackend;
    if (typeof record['read_only'] === 'boolean') decoded.readOnly = record['read_only'];
    const readOnlyReason = readNullableTrimmedStringValue(record['read_only_reason'], 'Hardware volume.read_only_reason');
    if (record['read_only_reason'] === null) decoded.readOnlyReason = null;
    else if (readOnlyReason !== null) decoded.readOnlyReason = readOnlyReason;
    return decoded;
};

const decodeNetworkAddress = (record: JsonObject): HardwareNetworkAddress => {
    const decoded: HardwareNetworkAddress = {};
    const type = readOptionalHardwareString(record, 'type', 'Hardware network address');
    const address = readOptionalHardwareString(record, 'address', 'Hardware network address');
    const netmask = readOptionalHardwareString(record, 'netmask', 'Hardware network address');
    if (type !== undefined) decoded.type = type;
    if (address !== undefined) decoded.address = address;
    if (netmask !== undefined) decoded.netmask = netmask;
    return decoded;
};

const decodeObjectArray = (value: JsonValue | undefined, label: string): JsonObject[] => {
    if (!Array.isArray(value)) throw new TypeError(`${label} must be an array`);
    return value.map((entry, index) => requireRecord(entry, `${label}[${String(index)}]`));
};

const decodeNetworkInterface = (record: JsonObject): HardwareNetworkInterface => {
    const decoded: HardwareNetworkInterface = {};
    const label = 'Hardware network interface';
    const deviceId = readOptionalHardwareString(record, 'device_id', label);
    const name = readOptionalHardwareString(record, 'name', label);
    const macAddress = readOptionalHardwareString(record, 'mac_address', label);
    const linkSpeedMbps = readOptionalHardwareNumber(record, 'link_speed_mbps', label);
    if (deviceId !== undefined) decoded.deviceId = deviceId;
    if (name !== undefined) decoded.name = name;
    if (macAddress !== undefined) decoded.macAddress = macAddress;
    if (record['addresses'] !== undefined) decoded.addresses = decodeObjectArray(record['addresses'], `${label}.addresses`).map(decodeNetworkAddress);
    if (linkSpeedMbps !== undefined) decoded.linkSpeedMbps = linkSpeedMbps;
    if (typeof record['is_up'] === 'boolean') decoded.isUp = record['is_up'];
    return decoded;
};

const decodeNetworkSpeed = (record: JsonObject): HardwareNetworkSpeed => {
    const decoded: HardwareNetworkSpeed = {};
    const uploadMbps = readOptionalHardwareNumber(record, 'upload_mbps', 'Hardware network speed');
    const downloadMbps = readOptionalHardwareNumber(record, 'download_mbps', 'Hardware network speed');
    const observedAtMs = readOptionalHardwareNumber(record, 'observed_at_ms', 'Hardware network speed');
    if (uploadMbps !== undefined) decoded.uploadMbps = uploadMbps;
    if (downloadMbps !== undefined) decoded.downloadMbps = downloadMbps;
    if (observedAtMs !== undefined) decoded.observedAtMs = observedAtMs;
    return decoded;
};

const decodeUptime = (record: JsonObject): HardwareUptimeSnapshot => {
    const decoded: HardwareUptimeSnapshot = {};
    const uptimeMs = readOptionalHardwareNumber(record, 'uptime_ms', 'Hardware snapshot.uptime');
    const bootTimeMs = readOptionalHardwareNumber(record, 'boot_time_ms', 'Hardware snapshot.uptime');
    if (uptimeMs !== undefined) decoded.uptimeMs = uptimeMs;
    if (bootTimeMs !== undefined) decoded.bootTimeMs = bootTimeMs;
    return decoded;
};

const decodeHardwareSnapshot = (value: ApiResponsePayload): HardwareSnapshotResponse => {
    const record = requireRecord(value, 'Hardware snapshot');
    const timestampMs = readRequiredNonNegativeIntegerValue(record['timestamp_ms'], 'Hardware snapshot.timestamp_ms');
    if (!isEpochMsNumber(timestampMs)) throw new TypeError('Hardware snapshot.timestamp_ms must be an epoch timestamp');
    const snapshot: HardwareSnapshotResponse = {
        timestampMs,
        summary: decodeSummary(requireRecord(record['summary'], 'Hardware snapshot.summary')),
        capabilities: decodeHardwareCapabilities(record['capabilities'])
    };
    const cpus = record['cpus'];
    if (cpus !== undefined && cpus !== null) snapshot.cpus = decodeObjectArray(cpus, 'Hardware snapshot.cpus').map((entry, index) => decodeCpu(entry, `Hardware snapshot.cpus[${String(index)}]`));
    const cpu = record['cpu'];
    if (cpu !== undefined && cpu !== null) snapshot.cpu = decodeCpu(cpu, 'Hardware snapshot.cpu');
    const memory = record['memory'];
    if (memory === null) snapshot.memory = null;
    else if (memory !== undefined) snapshot.memory = decodeMemory(requireRecord(memory, 'Hardware snapshot.memory'), 'Hardware snapshot.memory');
    const swap = record['swap'];
    if (swap === null) snapshot.swap = null;
    else if (swap !== undefined) snapshot.swap = decodeMemory(requireRecord(swap, 'Hardware snapshot.swap'), 'Hardware snapshot.swap');
    const uptime = record['uptime'];
    if (uptime !== undefined && uptime !== null) snapshot.uptime = decodeUptime(requireRecord(uptime, 'Hardware snapshot.uptime'));
    const operatingSystem = record['os'];
    if (operatingSystem !== undefined && operatingSystem !== null) snapshot.os = decodeHardwareOperatingSystemSnapshot(operatingSystem);
    const gpu = record['gpu'];
    if (gpu !== undefined && gpu !== null) {
        const gpuRecord = requireRecord(gpu, 'Hardware snapshot.gpu');
        snapshot.gpu = { gpus: decodeObjectArray(gpuRecord['gpus'], 'Hardware snapshot.gpu.gpus').map((entry, index) => decodeHardwareSnapshotGpu(entry, `Hardware snapshot.gpu.gpus[${String(index)}]`)) };
        const binding = gpuRecord['binding'];
        if (binding !== undefined && binding !== null) snapshot.gpu.binding = { devices: decodeObjectArray(requireRecord(binding, 'Hardware snapshot.gpu.binding')['devices'], 'Hardware snapshot.gpu.binding.devices').map((entry, index) => decodeHardwareSnapshotGpu(entry, `Hardware snapshot.gpu.binding.devices[${String(index)}]`)) };
    }
    const disk = record['disk'];
    if (disk !== undefined && disk !== null) snapshot.disk = decodeObjectArray(disk, 'Hardware snapshot.disk').map(decodeVolume);
    const network = record['network'];
    if (network !== undefined && network !== null) {
        const networkRecord = requireRecord(network, 'Hardware snapshot.network');
        snapshot.network = { interfaces: decodeObjectArray(networkRecord['interfaces'], 'Hardware snapshot.network.interfaces').map(decodeNetworkInterface) };
        const byDeviceId = networkRecord['by_device_id'];
        if (byDeviceId !== undefined && byDeviceId !== null) snapshot.network.byDeviceId = Object.fromEntries(Object.entries(requireRecord(byDeviceId, 'Hardware snapshot.network.by_device_id')).map(([deviceId, entry]) => [deviceId, decodeNetworkInterface(requireRecord(entry, `Hardware snapshot.network.by_device_id.${deviceId}`))]));
    }
    const networkSpeed = record['network_speed'];
    if (networkSpeed !== undefined && networkSpeed !== null) snapshot.networkSpeed = Object.fromEntries(Object.entries(requireRecord(networkSpeed, 'Hardware snapshot.network_speed')).map(([deviceId, entry]) => [deviceId, decodeNetworkSpeed(requireRecord(entry, `Hardware snapshot.network_speed.${deviceId}`))]));
    if (record['disk_speed'] === null) snapshot.diskSpeed = null;
    else if (record['disk_speed'] !== undefined) {
        const diskSpeed = requireRecord(record['disk_speed'], 'Hardware snapshot.disk_speed');
        snapshot.diskSpeed = { status: readNullableTrimmedStringValue(diskSpeed['status'], 'Hardware snapshot.disk_speed.status') ?? '' };
        const observedAtMs = readOptionalHardwareNumber(diskSpeed, 'observed_at_ms', 'Hardware snapshot.disk_speed');
        if (observedAtMs !== undefined) snapshot.diskSpeed.observedAtMs = observedAtMs;
    }
    return snapshot;
};

export { decodeHardwareCapabilities, decodeHardwareSnapshot };
