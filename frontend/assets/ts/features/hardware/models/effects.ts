/* SoAI - Hardware feature models effects [frontend/assets/ts/features/hardware/models/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { HardwareNetworkAddress, HardwareNetworkInterface } from '@core/api/contracts/hardwareContractTypes.ts';
import { resolveHardwareObservation } from '@core/api/contracts/hardwareComponentObservationContracts.ts';
import { isArray, isFiniteNumber, isObject, isString } from '@core/typeGuards.ts';
import { filterStringArrayValue } from '@core/types/payloadArrayReaders.ts';
import { DEFAULT_IGNORED_NETWORK_PREFIXES } from '@features/hardware/models/constants.ts';
import { buildVolumeModels, getCpuDevices, getGpuDevices, getNetworkInterfaces } from '@features/hardware/models/mappers.ts';
import { resolveNetworkSpeedEntry } from '@features/hardware/models/networkSpeed.ts';
import { getWindowsNetworkInventoryStatus, isVisibleNetworkInterfaceName } from '@features/hardware/models/networkVisibility.ts';
import type { HardwareModels, HardwareModelsOptions, HardwareSnapshot, NetworkInterfaceModel, NetworkInterfaceOptions, NetworkModelOptions, NetworkSpeedSnapshot } from '@features/hardware/models/types.ts';

const normalizeNetworkAddresses = (value: HardwareNetworkAddress[] | null | undefined): HardwareNetworkAddress[] => {
    if (!isArray(value)) {
        return [];
    }
    const addresses: HardwareNetworkAddress[] = [];
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
        const normalizedAddress: HardwareNetworkAddress = {};
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

const buildNetworkInterfaceModel = (iface: HardwareNetworkInterface, speeds: NetworkSpeedSnapshot | null | undefined, { ignorePrefixes = DEFAULT_IGNORED_NETWORK_PREFIXES, windowsInventoryStatus = null }: NetworkInterfaceOptions = {}): NetworkInterfaceModel | null => {
    const nameValue = iface?.name;
    const deviceIdValue = iface?.deviceId;
    if (!isString(nameValue) || !nameValue.trim()) {
        return null;
    }
    if (!isString(deviceIdValue) || !deviceIdValue.trim()) {
        return null;
    }

    const name = nameValue.trim();
    if (!isVisibleNetworkInterfaceName(name, windowsInventoryStatus, filterStringArrayValue(ignorePrefixes))) {
        return null;
    }

    const speedEntry = isObject(speeds) ? resolveNetworkSpeedEntry(speeds, name, deviceIdValue.trim()) : null;
    const dlCandidate = speedEntry?.downloadMbps;
    const ulCandidate = speedEntry?.uploadMbps;
    const observedCandidate = speedEntry ? Number(speedEntry.observedAtMs) : 0;

    const dlMbps = isFiniteNumber(dlCandidate) && dlCandidate >= 0 ? dlCandidate : undefined;
    const ulMbps = isFiniteNumber(ulCandidate) && ulCandidate >= 0 ? ulCandidate : undefined;
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
        .map((iface) => buildNetworkInterfaceModel(iface, speeds, { ignorePrefixes, windowsInventoryStatus: getWindowsNetworkInventoryStatus(snapshot) }))
        .filter((value): value is NetworkInterfaceModel => value !== null)
        .map((value) => ({ ...value, observationStatus: snapshot ? resolveHardwareObservation(snapshot, 'network_speed') : undefined }))
        .sort((firstValue, secondValue) => Math.max(secondValue.dlMbps ?? 0, secondValue.ulMbps ?? 0) - Math.max(firstValue.dlMbps ?? 0, firstValue.ulMbps ?? 0));

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
