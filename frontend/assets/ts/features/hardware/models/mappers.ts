/* SoAI - Hardware feature models mapping [frontend/assets/ts/features/hardware/models/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampPercent } from '@core/primitives/clampNumber.ts';
import { isFiniteNumber, isPlainObject, isString } from '@core/typeGuards.ts';
import { DEFAULT_IGNORED_FILESYSTEMS, DEFAULT_IGNORED_MOUNTS, DEFAULT_MIN_VOLUME_CAPACITY_GB } from '@features/hardware/models/constants.ts';
import { formatBytesValue } from '@features/hardware/Formatters.ts';
import type { CpuRaw, GPURaw, HardwareSnapshot, NetworkInterfaceRaw, VolumeModel, VolumeOptions, VolumeRaw } from '@features/hardware/models/types.ts';

const getStorageVolumes = (snapshot: HardwareSnapshot | null | undefined): VolumeRaw[] => {
    const disk = snapshot?.disk;
    return Array.isArray(disk) ? disk : [];
};

const isHardwareSnapshot = <T>(value: T): value is T & HardwareSnapshot => isPlainObject(value);

const getGpuOptionId = (gpu: GPURaw | null | undefined, fallbackIndex = 0): number => Number(gpu?.index ?? fallbackIndex);

const getCpuDevices = (snapshot: HardwareSnapshot | null | undefined): CpuRaw[] => {
    return Array.isArray(snapshot?.cpus) ? snapshot.cpus : [];
};

const isComputeGpuDevice = (gpu: GPURaw): boolean => {
    const displayAdapterType = gpu.displayAdapterType;
    return gpu.computeCapable !== false && !(isString(displayAdapterType) && displayAdapterType.trim());
};

const getGpuDevices = (snapshot: HardwareSnapshot | null | undefined): GPURaw[] => {
    return (Array.isArray(snapshot?.gpu?.gpus) ? snapshot.gpu.gpus : []).filter(isComputeGpuDevice);
};

const getNetworkInterfaces = (snapshot: HardwareSnapshot | null | undefined): NetworkInterfaceRaw[] => {
    return Array.isArray(snapshot?.network?.interfaces) ? snapshot.network.interfaces : [];
};

const isZfsVolume = (volume: VolumeRaw): boolean => {
    const backend = isString(volume.storageBackend) ? volume.storageBackend.trim().toLowerCase() : '';
    const filesystemType = isString(volume.fstype) ? volume.fstype.trim().toLowerCase() : '';
    return backend === 'zfs' || filesystemType === 'zfs';
};

const buildVolumeModel = (volume: VolumeRaw, { ignoredFilesystems = DEFAULT_IGNORED_FILESYSTEMS, ignoredMounts = DEFAULT_IGNORED_MOUNTS, minCapacityGb = DEFAULT_MIN_VOLUME_CAPACITY_GB }: VolumeOptions = {}): VolumeModel | null => {
    const deviceId = volume?.deviceId;
    const filesystem = volume?.filesystem;
    const mount = volume?.mount;
    if (!isString(deviceId) || !deviceId.trim()) {
        return null;
    }
    if (!isString(filesystem) || !filesystem.trim()) {
        return null;
    }
    if (!isString(mount) || !mount.trim()) {
        return null;
    }

    const totalBytes = Number(volume.totalBytes ?? 0);
    const usedBytes = Number(volume.usedBytes ?? 0);
    const freeBytes = Number(volume.freeBytes ?? 0);
    const percentUsed = Number(volume.percentUsed ?? 0);
    const zfsVolume = isZfsVolume(volume);

    if (!isFiniteNumber(totalBytes) || totalBytes <= 0) {
        return null;
    }
    const sizeGb = Math.max(0, totalBytes / 1024 ** 3);
    if (!zfsVolume && sizeGb < (minCapacityGb ?? DEFAULT_MIN_VOLUME_CAPACITY_GB)) {
        return null;
    }

    const fsLower = filesystem.toLowerCase();
    const typeLower = isString(volume.fstype) ? volume.fstype.toLowerCase() : '';
    if ((ignoredFilesystems ?? []).some((entry) => fsLower.includes(entry) || typeLower === entry)) {
        return null;
    }
    if ((ignoredMounts ?? []).some((prefix) => mount.startsWith(prefix))) {
        return null;
    }

    const normalizedPercent = isFiniteNumber(percentUsed) ? clampPercent(percentUsed) : 0;

    return {
        deviceId: deviceId.trim(),
        filesystem: filesystem.trim(),
        mount: mount.trim(),
        fstype: isString(volume.fstype) && volume.fstype.trim() ? volume.fstype.trim() : 'unknown',
        size: formatBytesValue(totalBytes),
        used: formatBytesValue(isFiniteNumber(usedBytes) && usedBytes >= 0 ? usedBytes : 0),
        available: formatBytesValue(isFiniteNumber(freeBytes) && freeBytes >= 0 ? freeBytes : 0),
        percentUsed: normalizedPercent,
        sizeGb,
        totalBytes,
        usedBytes: isFiniteNumber(usedBytes) && usedBytes >= 0 ? usedBytes : 0,
        freeBytes: isFiniteNumber(freeBytes) && freeBytes >= 0 ? freeBytes : 0,
        storageBackend: isString(volume.storageBackend) && volume.storageBackend.trim() ? volume.storageBackend.trim() : 'block',
        readOnly: volume.readOnly === true,
        readOnlyReason: isString(volume.readOnlyReason) && volume.readOnlyReason.trim() ? volume.readOnlyReason.trim() : null
    };
};

const buildVolumeModels = (snapshot: HardwareSnapshot | null | undefined, options: VolumeOptions = {}): VolumeModel[] =>
    getStorageVolumes(snapshot)
        .map((volume) => buildVolumeModel(volume, options))
        .filter((volume): volume is VolumeModel => volume !== null)
        .sort((firstValue, secondValue) => secondValue.sizeGb - firstValue.sizeGb);

export { getStorageVolumes, getGpuOptionId, getCpuDevices, getGpuDevices, getNetworkInterfaces, buildVolumeModel, buildVolumeModels, isHardwareSnapshot };
