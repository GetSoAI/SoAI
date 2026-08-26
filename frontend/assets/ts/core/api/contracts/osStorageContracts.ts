/* SoAI - Frontend OS storage response contracts [frontend/assets/ts/core/api/contracts/osStorageContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredFiniteNumberValue } from '@core/types/payloadNumberReaders.ts';
import { readRequiredBooleanValue, readRequiredEnumValue, readRequiredStringValue } from '@core/types/payloadValueReaders.ts';

type OsStorageBackend = 'block' | 'zfs';
type OsStorageFormatRecoveryState = 'ready' | 'unavailable' | 'identity_mismatch' | 'blocked';
type OsStorageFormatRecoveryReason = 'ready' | 'device_unavailable' | 'partition_unavailable' | 'identity_mismatch' | 'not_disk' | 'read_only' | 'mounted' | 'device_in_use' | 'invalid_payload' | 'unsupported_checkpoint';
const OS_STORAGE_FORMAT_RECOVERY_STATES: readonly OsStorageFormatRecoveryState[] = ['ready', 'unavailable', 'identity_mismatch', 'blocked'];
const OS_STORAGE_FORMAT_RECOVERY_REASONS: readonly OsStorageFormatRecoveryReason[] = ['ready', 'device_unavailable', 'partition_unavailable', 'identity_mismatch', 'not_disk', 'read_only', 'mounted', 'device_in_use', 'invalid_payload', 'unsupported_checkpoint'];
interface OsStorageFormatRecovery {
    requestId: string;
    taskId: string;
    devicePath: string | null;
    partitionPath: string;
    deviceFingerprint: string | null;
    requestedFilesystem: string | null;
    requestedLabel: string | null;
    requestedLabelValid: boolean;
    requestedAllowWipe: boolean;
    executionPhase: string;
    attemptCount: number;
    state: OsStorageFormatRecoveryState;
    reason: OsStorageFormatRecoveryReason;
}
interface OsStoragePartition {
    name: string;
    path: string;
    sizeBytes: number;
    filesystem: string | null;
    uuid: string | null;
    label: string | null;
    mountPoint: string | null;
    storageBackend: OsStorageBackend;
    readOnly: boolean;
    readOnlyReason: string | null;
    unmountAllowed: boolean;
    unmountBlockReason: string | null;
}
interface OsStorageBlockDevice {
    name: string;
    path: string;
    sizeBytes: number;
    deviceType: string;
    filesystem: string | null;
    uuid: string | null;
    label: string | null;
    mountPoint: string | null;
    model: string | null;
    serial: string | null;
    rotational: boolean | null;
    fingerprint: string;
    hasMountedFilesystems: boolean;
    partitions: OsStoragePartition[];
    storageBackend: OsStorageBackend;
    readOnly: boolean;
    readOnlyReason: string | null;
}
interface OsStorageZfsVolume {
    name: string;
    source: string;
    mountPoint: string;
    sizeBytes: number;
    usedBytes: number;
    freeBytes: number;
    filesystem: string;
    storageBackend: 'zfs';
    readOnly: boolean;
    readOnlyReason: string;
}
interface OsStorageFstabEntry {
    source: string;
    uuid: string | null;
    mountPoint: string;
    filesystem: string;
    options: string;
    dump: number;
    passNumber: number;
}
interface OsStorageStatusResponse {
    devices: OsStorageBlockDevice[];
    zfsVolumes: OsStorageZfsVolume[];
    formatRecoveries: OsStorageFormatRecovery[];
    timestampMs: number;
}
interface OsSystemStorageStatusResponse {
    blockDevices: OsStorageBlockDevice[];
    zfsVolumes: OsStorageZfsVolume[];
    timestampMs: number;
}
interface OsStorageDevicesResponse {
    devices: OsStorageBlockDevice[];
}
interface OsStorageDeviceResponse {
    device: OsStorageBlockDevice;
}
interface OsStoragePartitionsResponse {
    partitions: OsStoragePartition[];
}
interface OsStorageFstabResponse {
    entries: OsStorageFstabEntry[];
}

const nullableString = (value: ApiResponsePayload, label: string): string | null => (value === null ? null : readRequiredStringValue(value, label));
const nullableBoolean = (value: ApiResponsePayload, label: string): boolean | null => (value === null ? null : readRequiredBooleanValue(value, label));
const backend = (value: ApiResponsePayload, label: string): OsStorageBackend => {
    if (value !== 'block' && value !== 'zfs') throw new TypeError(`${label} must be block or zfs`);
    return value;
};
const array = (value: ApiResponsePayload, label: string): ApiResponsePayload[] => {
    if (!Array.isArray(value)) throw new TypeError(`${label} must be an array`);
    return [...value];
};
const decodeFormatRecovery = (value: ApiResponsePayload, label: string): OsStorageFormatRecovery => {
    const record = requireRecord(value, label);
    return {
        requestId: readRequiredStringValue(record['request_id'], `${label}.request_id`),
        taskId: readRequiredStringValue(record['task_id'], `${label}.task_id`),
        devicePath: nullableString(record['device_path'] ?? null, `${label}.device_path`),
        partitionPath: readRequiredStringValue(record['partition_path'], `${label}.partition_path`),
        deviceFingerprint: nullableString(record['device_fingerprint'] ?? null, `${label}.device_fingerprint`),
        requestedFilesystem: nullableString(record['requested_filesystem'] ?? null, `${label}.requested_filesystem`),
        requestedLabel: nullableString(record['requested_label'] ?? null, `${label}.requested_label`),
        requestedLabelValid: readRequiredBooleanValue(record['requested_label_valid'], `${label}.requested_label_valid`),
        requestedAllowWipe: readRequiredBooleanValue(record['requested_allow_wipe'], `${label}.requested_allow_wipe`),
        executionPhase: readRequiredStringValue(record['execution_phase'], `${label}.execution_phase`),
        attemptCount: readRequiredFiniteNumberValue(record['attempt_count'], `${label}.attempt_count`),
        state: readRequiredEnumValue(record['state'], `${label}.state`, OS_STORAGE_FORMAT_RECOVERY_STATES),
        reason: readRequiredEnumValue(record['reason'], `${label}.reason`, OS_STORAGE_FORMAT_RECOVERY_REASONS)
    };
};
const decodePartition = (value: ApiResponsePayload, label: string): OsStoragePartition => {
    const record = requireRecord(value, label);
    return { name: readRequiredStringValue(record['name'], `${label}.name`), path: readRequiredStringValue(record['path'], `${label}.path`), sizeBytes: readRequiredFiniteNumberValue(record['size_bytes'], `${label}.size_bytes`), filesystem: nullableString(record['filesystem'] ?? null, `${label}.filesystem`), uuid: nullableString(record['uuid'] ?? null, `${label}.uuid`), label: nullableString(record['label'] ?? null, `${label}.label`), mountPoint: nullableString(record['mount_point'] ?? null, `${label}.mount_point`), storageBackend: backend(record['storage_backend'], `${label}.storage_backend`), readOnly: readRequiredBooleanValue(record['read_only'], `${label}.read_only`), readOnlyReason: nullableString(record['read_only_reason'] ?? null, `${label}.read_only_reason`), unmountAllowed: readRequiredBooleanValue(record['unmount_allowed'], `${label}.unmount_allowed`), unmountBlockReason: nullableString(record['unmount_block_reason'] ?? null, `${label}.unmount_block_reason`) };
};
const decodeBlockDevice = (value: ApiResponsePayload, label: string): OsStorageBlockDevice => {
    const record = requireRecord(value, label);
    return {
        name: readRequiredStringValue(record['name'], `${label}.name`),
        path: readRequiredStringValue(record['path'], `${label}.path`),
        sizeBytes: readRequiredFiniteNumberValue(record['size_bytes'], `${label}.size_bytes`),
        deviceType: readRequiredStringValue(record['device_type'], `${label}.device_type`),
        filesystem: nullableString(record['filesystem'] ?? null, `${label}.filesystem`),
        uuid: nullableString(record['uuid'] ?? null, `${label}.uuid`),
        label: nullableString(record['label'] ?? null, `${label}.label`),
        mountPoint: nullableString(record['mount_point'] ?? null, `${label}.mount_point`),
        model: nullableString(record['model'] ?? null, `${label}.model`),
        serial: nullableString(record['serial'] ?? null, `${label}.serial`),
        rotational: nullableBoolean(record['rotational'] ?? null, `${label}.rotational`),
        fingerprint: readRequiredStringValue(record['fingerprint'], `${label}.fingerprint`),
        hasMountedFilesystems: readRequiredBooleanValue(record['has_mounted_filesystems'], `${label}.has_mounted_filesystems`),
        partitions: array(record['partitions'], `${label}.partitions`).map((entry, index) => decodePartition(entry, `${label}.partitions[${String(index)}]`)),
        storageBackend: backend(record['storage_backend'], `${label}.storage_backend`),
        readOnly: readRequiredBooleanValue(record['read_only'], `${label}.read_only`),
        readOnlyReason: nullableString(record['read_only_reason'] ?? null, `${label}.read_only_reason`)
    };
};
const decodeZfsVolume = (value: ApiResponsePayload, label: string): OsStorageZfsVolume => {
    const record = requireRecord(value, label);
    if (record['storage_backend'] !== 'zfs') throw new TypeError(`${label}.storage_backend must be zfs`);
    return { name: readRequiredStringValue(record['name'], `${label}.name`), source: readRequiredStringValue(record['source'], `${label}.source`), mountPoint: readRequiredStringValue(record['mount_point'], `${label}.mount_point`), sizeBytes: readRequiredFiniteNumberValue(record['size_bytes'], `${label}.size_bytes`), usedBytes: readRequiredFiniteNumberValue(record['used_bytes'], `${label}.used_bytes`), freeBytes: readRequiredFiniteNumberValue(record['free_bytes'], `${label}.free_bytes`), filesystem: readRequiredStringValue(record['filesystem'], `${label}.filesystem`), storageBackend: 'zfs', readOnly: readRequiredBooleanValue(record['read_only'], `${label}.read_only`), readOnlyReason: readRequiredStringValue(record['read_only_reason'], `${label}.read_only_reason`) };
};
const decodeFstabEntry = (value: ApiResponsePayload, label: string): OsStorageFstabEntry => {
    const record = requireRecord(value, label);
    return { source: readRequiredStringValue(record['source'], `${label}.source`), uuid: nullableString(record['uuid'] ?? null, `${label}.uuid`), mountPoint: readRequiredStringValue(record['mount_point'], `${label}.mount_point`), filesystem: readRequiredStringValue(record['filesystem'], `${label}.filesystem`), options: readRequiredStringValue(record['options'], `${label}.options`), dump: readRequiredFiniteNumberValue(record['dump'], `${label}.dump`), passNumber: readRequiredFiniteNumberValue(record['pass_num'], `${label}.pass_num`) };
};
const decodeStorageDevices = (value: ApiResponsePayload, key: 'devices' | 'block_devices', label: string): OsStorageBlockDevice[] => {
    return array(value, `${label}.${key}`).map((entry, index) => decodeBlockDevice(entry, `${label}.${key}[${String(index)}]`));
};
const decodeStorageVolumes = (value: ApiResponsePayload, label: string): OsStorageZfsVolume[] => {
    return array(value, `${label}.zfs_volumes`).map((entry, index) => decodeZfsVolume(entry, `${label}.zfs_volumes[${String(index)}]`));
};
const decodeOsStorageStatus = (value: ApiResponsePayload): OsStorageStatusResponse => {
    const record = requireRecord(value, 'OS storage status');
    return { devices: decodeStorageDevices(record['devices'], 'devices', 'OS storage status'), zfsVolumes: decodeStorageVolumes(record['zfs_volumes'], 'OS storage status'), formatRecoveries: array(record['format_recoveries'], 'OS storage status.format_recoveries').map((entry, index) => decodeFormatRecovery(entry, `OS storage status.format_recoveries[${String(index)}]`)), timestampMs: readRequiredFiniteNumberValue(record['timestamp_ms'], 'OS storage status.timestamp_ms') };
};
const decodeOsSystemStorageStatus = (value: ApiResponsePayload): OsSystemStorageStatusResponse => {
    const record = requireRecord(value, 'OS system storage status');
    return { blockDevices: decodeStorageDevices(record['block_devices'], 'block_devices', 'OS system storage status'), zfsVolumes: decodeStorageVolumes(record['zfs_volumes'], 'OS system storage status'), timestampMs: readRequiredFiniteNumberValue(record['timestamp_ms'], 'OS system storage status.timestamp_ms') };
};
const decodeOsStorageDevices = (value: ApiResponsePayload): OsStorageDevicesResponse => {
    const record = requireRecord(value, 'OS storage devices');
    return { devices: array(record['devices'], 'OS storage devices.devices').map((entry, index) => decodeBlockDevice(entry, `OS storage devices.devices[${String(index)}]`)) };
};
const decodeOsStorageDevice = (value: ApiResponsePayload): OsStorageDeviceResponse => {
    const record = requireRecord(value, 'OS storage device');
    return { device: decodeBlockDevice(record['device'], 'OS storage device.device') };
};
const decodeOsStoragePartitions = (value: ApiResponsePayload): OsStoragePartitionsResponse => {
    const record = requireRecord(value, 'OS storage partitions');
    return { partitions: array(record['partitions'], 'OS storage partitions.partitions').map((entry, index) => decodePartition(entry, `OS storage partitions.partitions[${String(index)}]`)) };
};
const decodeOsStorageFstab = (value: ApiResponsePayload): OsStorageFstabResponse => {
    const record = requireRecord(value, 'OS storage fstab');
    return { entries: array(record['entries'], 'OS storage fstab.entries').map((entry, index) => decodeFstabEntry(entry, `OS storage fstab.entries[${String(index)}]`)) };
};

export { decodeOsStorageDevice, decodeOsStorageDevices, decodeOsStorageFstab, decodeOsStoragePartitions, decodeOsStorageStatus, decodeOsSystemStorageStatus };
export type { OsStorageBackend, OsStorageBlockDevice, OsStorageDeviceResponse, OsStorageDevicesResponse, OsStorageFormatRecovery, OsStorageFormatRecoveryReason, OsStorageFormatRecoveryState, OsStorageFstabEntry, OsStorageFstabResponse, OsStoragePartition, OsStoragePartitionsResponse, OsStorageStatusResponse, OsStorageZfsVolume, OsSystemStorageStatusResponse };
