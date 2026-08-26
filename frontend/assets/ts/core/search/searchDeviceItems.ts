/* SoAI - Shared search device items [frontend/assets/ts/core/search/searchDeviceItems.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString, toTrimmedStringOrNull } from '@core/normalize.ts';
import { isFiniteNumber, isNullOrUndefined } from '@core/typeGuards.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatInvariantNumber } from '@core/localization/public.ts';
import { formatBytes } from '@core/primitives/byteSize.ts';
import type { DeviceResultParameters, SearchItem } from '@core/search/searchTypes.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';

type ComponentKey = 'cpu' | 'gpu' | 'disk' | 'network';

interface CpuDeviceSearchInput {
    id: string;
    identifier: string | null;
    name: string;
    physicalCores?: number | undefined;
    logicalCores?: number | undefined;
    architecture?: string | undefined;
}
interface GpuDeviceSearchInput {
    id: number;
    gpuIndex: number;
    name: string;
    vendor?: string | undefined;
    type?: string | undefined;
    memoryTotalMb?: number | undefined;
}
interface VolumeDeviceSearchInput {
    identifier: string;
    name: string;
    mount?: string | undefined;
    filesystem?: string | undefined;
    totalBytes?: number | undefined;
    totalGb?: number | undefined;
    percentUsed?: number | undefined;
}
interface NetworkDeviceSearchInput {
    id: string;
    identifier: string;
    name: string;
    macAddress?: string | undefined;
    addresses?: ReadonlyArray<{ address?: string | null | undefined }> | undefined;
}

const COMPONENT_ICON_MAP: Readonly<Record<ComponentKey, IconName>> = Object.freeze({
    cpu: 'device-cpu',
    gpu: 'device-gpu',
    disk: 'device-storage',
    network: 'device-network'
});

const isComponentKey = (value: string): value is ComponentKey => value === 'cpu' || value === 'gpu' || value === 'disk' || value === 'network';

const resolveComponentBadge = (componentKey: ComponentKey): string => {
    switch (componentKey) {
        case 'cpu':
            return i18n.t('hardware.components.cpu');
        case 'gpu':
            return i18n.t('hardware.components.gpu');
        case 'disk':
            return i18n.t('hardware.components.volume');
        case 'network':
            return i18n.t('hardware.components.network');
    }
};

const createDeviceResult = (parameters: DeviceResultParameters): SearchItem | null => {
    const { id, name, description, component, identifier = null, metric, badge, icon, extra = {} } = parameters;
    if (!id || !name || !component || !metric) return null;
    const normalizedComponent = String(component).toLowerCase();
    const componentKey = isComponentKey(normalizedComponent) ? normalizedComponent : null;
    const computedBadge = badge !== undefined ? badge : componentKey ? resolveComponentBadge(componentKey) : undefined;
    const computedIcon = icon !== undefined ? icon : componentKey ? COMPONENT_ICON_MAP[componentKey] : undefined;
    const result: SearchItem = {
        id,
        name,
        description,
        type: 'devices',
        category: 'devices',
        component: normalizedComponent,
        metric
    };
    if (computedBadge !== undefined) result.badge = computedBadge;
    if (computedIcon !== undefined) result.icon = computedIcon;
    if (!isNullOrUndefined(identifier)) result.identifier = identifier;
    if (extra?.gpuIndex !== undefined) result.gpuIndex = extra.gpuIndex;
    return result;
};

const buildCpuDeviceResult = (device: CpuDeviceSearchInput): SearchItem | null => {
    const physicalCores = Number(device.physicalCores);
    const logicalCores = Number(device.logicalCores);
    const name = toTrimmedStringOrNull(device.name) || i18n.t('hardware.components.cpu');
    const coresLabel = isFiniteNumber(physicalCores) && physicalCores > 0 ? i18n.t('search.deviceDescriptions.cpuCores', { count: physicalCores }) : null;
    const threadsLabel = isFiniteNumber(logicalCores) && logicalCores > 0 ? i18n.t('search.deviceDescriptions.cpuThreads', { count: logicalCores }) : null;
    const description = [coresLabel, threadsLabel, device.architecture].filter(Boolean).join(' · ') || null;
    const result = createDeviceResult({
        id: !isNullOrUndefined(device.id) ? String(device.id) : 'cpu',
        name,
        description,
        component: 'cpu',
        metric: 'usage',
        identifier: !isNullOrUndefined(device.identifier) ? String(device.identifier) : null,
        badge: i18n.t('hardware.components.cpu'),
        icon: 'device-cpu'
    });
    if (result) result.alias = ['cpu', 'processor', device.architecture, device.name].filter(Boolean).join(' ');
    return result;
};

const buildGpuDeviceResult = (device: GpuDeviceSearchInput): SearchItem | null => {
    const idValue = device.id;
    const gpuIndexValue = device.gpuIndex;
    const index = typeof idValue === 'number' && Number.isInteger(idValue) ? idValue : Number(gpuIndexValue);
    if (!Number.isInteger(index) || index < 0) return null;
    const name = toTrimmedStringOrNull(device.name) || i18n.t('hardware.components.gpuIndexed', { index });
    const memoryTotalMb = Number(device.memoryTotalMb);
    const memoryLabel = isFiniteNumber(memoryTotalMb) && memoryTotalMb > 0 ? i18n.t('search.deviceDescriptions.gpuMemory', { amount: `${formatInvariantNumber(memoryTotalMb / 1024, { maximumFractionDigits: 1 })} GB` }) : null;
    const description = [device.vendor || device.type, memoryLabel].filter(Boolean).join(' · ') || null;
    const result = createDeviceResult({
        id: `gpu-${index}`,
        name,
        description,
        component: 'gpu',
        metric: 'usage',
        identifier: String(index),
        badge: i18n.t('hardware.components.gpu'),
        icon: 'device-gpu',
        extra: { gpuIndex: index }
    });
    if (result) {
        result.alias = ['gpu', 'graphics', 'video', device.vendor || device.type, device.name].filter(Boolean).join(' ');
    }
    return result;
};

const buildVolumeDeviceResult = (device: VolumeDeviceSearchInput): SearchItem | null => {
    const mount = toTrimmedStringOrNull(device.mount);
    const filesystem = toTrimmedStringOrNull(device.filesystem);
    const identifier = toTrimmedStringOrNull(device.identifier);
    if (!mount && !filesystem && !identifier) return null;
    const id = identifier || mount || filesystem;
    if (!id) return null;
    const totalBytesCandidates: Array<number | null> = [Number(device.totalBytes), isFiniteNumber(Number(device.totalGb)) ? Number(device.totalGb) * 1024 ** 3 : null];
    let totalBytesCandidate: number | null = null;
    totalBytesCandidates.forEach((value) => {
        if (totalBytesCandidate !== null) return;
        if (isFiniteNumber(value) && value > 0) totalBytesCandidate = value;
    });
    if (!isFiniteNumber(totalBytesCandidate) || totalBytesCandidate <= 0) return null;
    const usedPercentCandidate = [device.percentUsed].find((value) => isFiniteNumber(value) && value >= 0);
    const formattedTotal = formatBytes(totalBytesCandidate);
    const totalLabel = i18n.t('search.deviceDescriptions.storageTotal', { size: formattedTotal });
    const usedLabel = isFiniteNumber(usedPercentCandidate) ? i18n.t('search.deviceDescriptions.storageUsed', { percent: formatInvariantNumber(usedPercentCandidate, { maximumFractionDigits: 1 }) }) : null;
    const description = [totalLabel, filesystem, usedLabel].filter(Boolean).join(' · ') || null;
    const name = toTrimmedStringOrNull(device.name);
    if (!name) return null;
    const result = createDeviceResult({
        id: `disk::${id}`,
        name,
        description,
        component: 'disk',
        metric: 'disk_usage',
        identifier: id,
        badge: i18n.t('hardware.components.volume'),
        icon: 'device-storage'
    });
    if (result) result.alias = ['volume', 'disk', 'storage', name, id, filesystem, mount].filter(Boolean).join(' ');
    return result;
};

const buildNetworkDeviceResult = (device: NetworkDeviceSearchInput): SearchItem | null => {
    const preferredId = toTrimmedStringOrNull(device.identifier);
    const rawName = toTrimmedStringOrNull(device.name);
    const id = preferredId || toTrimmedStringOrNull(device.id);
    if (!id || !rawName) return null;
    const name = rawName;
    const mac = toTrimmedString(device.macAddress);
    const description = mac || null;
    const resolvedId = id;
    const result = createDeviceResult({
        id: `network::${resolvedId}`,
        name,
        description,
        component: 'network',
        metric: 'network_download',
        identifier: resolvedId,
        badge: i18n.t('hardware.components.network'),
        icon: 'device-network'
    });
    if (result) {
        const aliases = ['network', 'nic', 'interface', name, id, mac];
        if (device.addresses) {
            device.addresses.forEach((entry) => {
                if (typeof entry.address === 'string') aliases.push(toTrimmedString(entry.address));
            });
        }
        result.alias = aliases.filter(Boolean).join(' ');
    }
    return result;
};

export { createDeviceResult, buildCpuDeviceResult, buildGpuDeviceResult, buildVolumeDeviceResult, buildNetworkDeviceResult };
