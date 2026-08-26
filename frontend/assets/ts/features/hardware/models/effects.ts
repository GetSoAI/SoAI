/* SoAI - Hardware feature models effects [frontend/assets/ts/features/hardware/models/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isFiniteNumber, isObject, isString } from '@core/typeGuards.ts';
import { filterStringArrayValue } from '@core/types/payloadArrayReaders.ts';
import { DEFAULT_IGNORED_NETWORK_PREFIXES } from '@features/hardware/models/constants.ts';
import { buildVolumeModels, getCpuDevices, getGpuDevices, getNetworkInterfaces } from '@features/hardware/models/mappers.ts';
import { resolveNetworkSpeedEntry } from '@features/hardware/models/networkSpeed.ts';
import type { HardwareModels, HardwareModelsOptions, HardwareSnapshot, NetworkAddress, NetworkInterfaceModel, NetworkInterfaceRaw, NetworkInterfaceOptions, NetworkModelOptions, NetworkSpeedSnapshot } from '@features/hardware/models/types.ts';

const normalizeNetworkAddresses = (value: NetworkAddress[] | null | undefined): NetworkAddress[] => {
    if (!isArray(value)) {
        return [];
    }
    const addresses: NetworkAddress[] = [];
    for (const entry of value) {
        if (!entry || typeof entry !== 'object') {
            continue;
        }
        const type = isString(entry.type) ? entry.type.toLowerCase() : undefined;
        const address = isString(entry.address) ? entry.address.trim() : undefined;
        const netmask = isString(entry.netmask) ? entry.netmask : undefined;
        if (!type && !address) {
            continue;
        }
        const normalizedAddress: NetworkAddress = {};
        if (type !== undefined) {
            normalizedAddress.type = type;
        }
        if (address !== undefined) {
            normalizedAddress.address = address;
        }
        if (netmask !== undefined) {
            normalizedAddress.netmask = netmask;
        }
        addresses.push(normalizedAddress);
    }
    return addresses;
};

const buildNetworkInterfaceModel = (iface: NetworkInterfaceRaw, speeds: NetworkSpeedSnapshot | null | undefined, { ignorePrefixes = DEFAULT_IGNORED_NETWORK_PREFIXES }: NetworkInterfaceOptions = {}): NetworkInterfaceModel | null => {
    const nameValue = iface?.name;
    const deviceIdValue = iface?.deviceId;
    if (!isString(nameValue) || !nameValue.trim()) {
        return null;
    }
    if (!isString(deviceIdValue) || !deviceIdValue.trim()) {
        return null;
    }

    const name = nameValue.trim();
    const normalizedName = name.toLowerCase();
    const ignored = filterStringArrayValue(ignorePrefixes).map((value) => value.toLowerCase());
    if (ignored.some((prefix) => normalizedName.startsWith(prefix))) {
        return null;
    }

    const speedEntry = isObject(speeds) ? resolveNetworkSpeedEntry(speeds, name, deviceIdValue.trim()) : null;
    const dlCandidate = speedEntry ? Number(speedEntry.downloadMbps) : 0;
    const ulCandidate = speedEntry ? Number(speedEntry.uploadMbps) : 0;
    const observedCandidate = speedEntry ? Number(speedEntry.observedAtMs) : 0;

    const dlMbps = isFiniteNumber(dlCandidate) && dlCandidate >= 0 ? dlCandidate : 0;
    const ulMbps = isFiniteNumber(ulCandidate) && ulCandidate >= 0 ? ulCandidate : 0;
    const observedAtMs = isFiniteNumber(observedCandidate) && observedCandidate > 0 ? observedCandidate : 0;
    const linkSpeedCandidate = Number(iface.linkSpeedMbps);
    const linkSpeedMbps = isFiniteNumber(linkSpeedCandidate) && linkSpeedCandidate > 0 ? linkSpeedCandidate : 0;
    const isUp = typeof iface.isUp === 'boolean' ? iface.isUp : null;

    const addresses = normalizeNetworkAddresses(iface.addresses);
    const primaryAddr = addresses.find((entry) => entry?.type === 'ipv4') || addresses.find((entry) => entry?.address) || null;
    const secondaryAddr = addresses.find((entry) => entry?.type === 'ipv6') || null;

    const mac = isString(iface.macAddress) && iface.macAddress.trim() ? iface.macAddress.trim() : null;

    return {
        name,
        deviceId: deviceIdValue.trim(),
        addresses,
        primaryAddr,
        secondaryAddr,
        mac,
        dlMbps,
        ulMbps,
        observedAtMs,
        linkSpeedMbps,
        isUp
    };
};

const buildNetworkInterfaceModels = (snapshot: HardwareSnapshot | null | undefined, { speeds = snapshot?.networkSpeed, ignorePrefixes = DEFAULT_IGNORED_NETWORK_PREFIXES }: NetworkModelOptions = {}): NetworkInterfaceModel[] =>
    getNetworkInterfaces(snapshot)
        .map((iface) => buildNetworkInterfaceModel(iface, speeds, { ignorePrefixes }))
        .filter((value): value is NetworkInterfaceModel => value !== null)
        .sort((firstValue, secondValue) => Math.max(secondValue.dlMbps, secondValue.ulMbps) - Math.max(firstValue.dlMbps, firstValue.ulMbps));

const buildHardwareModels = (snapshot: HardwareSnapshot | null | undefined, options: HardwareModelsOptions = {}): HardwareModels => {
    return {
        cpus: getCpuDevices(snapshot),
        gpus: getGpuDevices(snapshot),
        volumes: buildVolumeModels(snapshot, options.volumes),
        networkInterfaces: buildNetworkInterfaceModels(snapshot, {
            speeds: options.network?.speeds ?? snapshot?.networkSpeed,
            ignorePrefixes: options.network?.ignorePrefixes
        })
    };
};

export { normalizeNetworkAddresses, buildNetworkInterfaceModel, buildNetworkInterfaceModels, buildHardwareModels };
