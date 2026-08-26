/* SoAI - Hardware feature contributor [frontend/assets/ts/features/hardware/search/contributor.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { SEARCH_SOURCE_HARDWARE, type SearchIndexContributor } from '@core/search/protocols.ts';
import { isString } from '@core/typeGuards.ts';
import { i18n } from '@core/i18n/index.ts';
import { buildCpuDeviceResult, buildGpuDeviceResult, buildNetworkDeviceResult, buildVolumeDeviceResult } from '@core/search/searchDeviceItems.ts';
import type { SearchItem } from '@core/search/searchTypes.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isJsonObjectMapValue } from '@core/types/runtimeCollectionGuards.ts';
import { DEFAULT_IGNORED_NETWORK_PREFIXES } from '@features/hardware/models/constants.ts';
import { buildHardwareModels } from '@features/hardware/models/effects.ts';

const normalizeHardwareSnapshotForSearchIndex = (snapshot: JsonObject): SearchItem[] => {
    const results: SearchItem[] = [];
    const seen = new Set<string>();

    const push = (item: SearchItem | null): void => {
        if (!item || !item.id) {
            return;
        }
        if (seen.has(item.id)) {
            return;
        }
        seen.add(item.id);
        results.push(item);
    };

    const hardware = buildHardwareModels(snapshot, {
        network: {
            speeds: isJsonObjectMapValue(snapshot['networkSpeed']) ? snapshot['networkSpeed'] : undefined,
            ignorePrefixes: DEFAULT_IGNORED_NETWORK_PREFIXES
        }
    });

    hardware.cpus.forEach((cpu, index) => {
        const cpuRec = cpu;
        const socketIdValue = cpuRec.socketId;
        const socketId = typeof socketIdValue === 'number' && Number.isFinite(socketIdValue) ? String(socketIdValue) : isString(socketIdValue) && socketIdValue.trim() ? socketIdValue.trim() : null;
        const fallback = index === 0 ? i18n.t('hardware.components.cpu') : socketId ? i18n.t('hardware.components.cpuIndexed', { index: socketId }) : i18n.t('hardware.components.cpuIndexed', { index });
        const id = socketId ? `cpu-${socketId}` : index === 0 ? 'cpu' : `cpu-${index}`;
        const identifier = socketId ? socketId : index === 0 ? 'cpu' : null;
        push(
            buildCpuDeviceResult({
                ...cpuRec,
                name: toTrimmedString(cpuRec['name']) || fallback,
                id,
                identifier
            })
        );
    });

    hardware.gpus.forEach((gpu, index) => {
        const gpuRec = gpu;
        const indexValue = gpuRec['index'];
        const idValue = gpuRec['id'];
        const gid = typeof indexValue === 'number' && Number.isInteger(indexValue) ? indexValue : typeof idValue === 'number' && Number.isInteger(idValue) ? idValue : index;
        const name = toTrimmedString(gpuRec['name']) || i18n.t('hardware.components.gpuIndexed', { index: gid });
        push(buildGpuDeviceResult({ ...gpuRec, id: gid, gpuIndex: gid, name }));
    });

    hardware.volumes.forEach((volume) => {
        const volRec = volume;
        const id = toTrimmedString(volRec.deviceId) || toTrimmedString(volRec.mount) || toTrimmedString(volRec.filesystem);
        if (!id) {
            return;
        }
        const name = toTrimmedString(volRec.mount) || toTrimmedString(volRec.filesystem) || id;
        push(buildVolumeDeviceResult({ ...volRec, identifier: id, name }));
    });

    hardware.networkInterfaces.forEach((iface) => {
        const ifaceRec = iface;
        const id = toTrimmedString(ifaceRec.deviceId) || toTrimmedString(ifaceRec.name);
        if (!id) {
            return;
        }
        const name = toTrimmedString(ifaceRec.name) || id;
        const addresses = ifaceRec.addresses.map((address) => ({
            type: address.type ?? null,
            address: address.address ?? null,
            netmask: address.netmask ?? null
        }));
        push(
            buildNetworkDeviceResult({
                id,
                identifier: id,
                name,
                addresses
            })
        );
    });

    return results;
};

const createHardwareSearchContributor = (): SearchIndexContributor => {
    return {
        id: 'features.hardware.search',
        bucket: 'devices',
        source: SEARCH_SOURCE_HARDWARE,
        index: (resourceValue: JsonValue): SearchItem[] => (isJsonObject(resourceValue) ? normalizeHardwareSnapshotForSearchIndex(resourceValue) : [])
    };
};

export { createHardwareSearchContributor, normalizeHardwareSnapshotForSearchIndex };
