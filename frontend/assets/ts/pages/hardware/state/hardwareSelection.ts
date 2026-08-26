/* SoAI - Hardware page selection [frontend/assets/ts/pages/hardware/state/hardwareSelection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { encodeSegment } from '@core/identifiers.ts';
import { toString, toTrimmedString } from '@core/normalize.ts';
import { hasFunctionProperty, isArray, isNullOrUndefined, isObject } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isStringRecordValue } from '@core/types/runtimeCollectionGuards.ts';
import { readRuntimeFiniteNumberOrFallbackValue } from '@core/types/numberCoercionReaders.ts';
import { buildNetworkInterfaceModels, buildVolumeModels, DEFAULT_IGNORED_NETWORK_PREFIXES, normalizeHistoryComponent, normalizeIdentifier, type HardwareSnapshot } from '@features/hardware/public.ts';
import type { DeviceSelection, MetricConfigEntry, QuerySelection } from '@pages/hardware/types.ts';

type MetricConfig = Record<string, MetricConfigEntry>;

type RouterQueryParametersProvider = {
    getQueryParameters?: () => Record<string, string> | null;
};

const isRouterQueryParametersProvider = <T>(value: T): value is T & RouterQueryParametersProvider => {
    if (!isObject(value) || isArray(value)) return false;
    return !('getQueryParameters' in value) || isNullOrUndefined(value.getQueryParameters) || hasFunctionProperty(value, 'getQueryParameters');
};

const STR_GPU = 'gpu';
const STR_CPU = 'cpu';
const STR_DISK = 'disk';
const STR_NETWORK = 'network';
const STR_USAGE = 'usage';

const RE_GPU = /^gpu(?:\s*[-#:·]*\s*|::)(\d+)/i;
const RE_TYPE = /^(cpu|gpu|disk|network)\b/i;

const resolveHistoryComponents = (lastSnapshot: HardwareSnapshot | null | undefined, supportedHistoryComponents: string[] | undefined): string[] => {
    if (supportedHistoryComponents?.length) {
        return supportedHistoryComponents.map(normalizeHistoryComponent);
    }
    const components = new Set([STR_CPU, STR_GPU]);
    if (buildVolumeModels(lastSnapshot).length) {
        components.add(STR_DISK);
    }
    if (
        buildNetworkInterfaceModels(lastSnapshot, {
            ignorePrefixes: DEFAULT_IGNORED_NETWORK_PREFIXES
        }).length
    ) {
        components.add(STR_NETWORK);
    }
    return Array.from(components);
};

const isHistoryComponentSupported = (lastSnapshot: HardwareSnapshot | null | undefined, supportedHistoryComponents: string[] | undefined, component: JsonValue | null | undefined): boolean => {
    return resolveHistoryComponents(lastSnapshot, supportedHistoryComponents).includes(normalizeHistoryComponent(toString(component)));
};

const resolveSupportedHistoryComponent = (lastSnapshot: HardwareSnapshot | null | undefined, supportedHistoryComponents: string[] | undefined, component: JsonValue | null | undefined): string => {
    const normalized = normalizeHistoryComponent(toString(component));
    if (!normalized) throw new Error('History component is required');
    if (!isHistoryComponentSupported(lastSnapshot, supportedHistoryComponents, normalized)) {
        throw new Error(`Unsupported history component '${String(component)}'`);
    }
    return normalized;
};

const buildDeviceSelectionValue = (component: JsonValue | null | undefined, identifier: JsonValue | null = null): string => {
    const normalized = normalizeHistoryComponent(toString(component));
    if (normalized === STR_GPU) {
        const index = Math.max(0, Math.floor(readRuntimeFiniteNumberOrFallbackValue(identifier, 0)));
        return `${STR_GPU}-${index}`;
    }
    return !isNullOrUndefined(identifier) ? `${normalized}::${encodeSegment(String(identifier))}` : normalized;
};

const parseDeviceSelection = (value: JsonValue | null | undefined, lastSnapshot: HardwareSnapshot | null | undefined, supportedHistoryComponents: string[] | undefined): DeviceSelection => {
    const raw = toTrimmedString(toString(value));
    const normalizedRaw = normalizeHistoryComponent(raw);
    if (!raw || normalizedRaw === STR_CPU) {
        return { type: STR_CPU, identifier: null, identifierKey: null, gpuIndex: null, value: STR_CPU };
    }

    const gpuMatch = raw.match(RE_GPU) || (raw.startsWith('gpu-') ? [null, raw.split('-')[1]] : null);
    if (gpuMatch) {
        const index = Math.max(0, Math.floor(readRuntimeFiniteNumberOrFallbackValue(gpuMatch[1], 0)));
        return {
            type: STR_GPU,
            identifier: index,
            identifierKey: normalizeIdentifier(STR_GPU, String(index)),
            gpuIndex: index,
            value: buildDeviceSelectionValue(STR_GPU, index)
        };
    }

    if (!raw.includes('::')) {
        const typeMatch = raw.match(RE_TYPE);
        if (!typeMatch) {
            throw new Error(`Invalid hardware device selection '${raw}'`);
        }
        const resolvedType = resolveSupportedHistoryComponent(lastSnapshot, supportedHistoryComponents, typeMatch[1]);
        if (resolvedType === STR_CPU) {
            return { type: STR_CPU, identifier: null, identifierKey: null, gpuIndex: null, value: STR_CPU };
        }
        if (resolvedType === STR_GPU) {
            const index = 0;
            return {
                type: STR_GPU,
                identifier: index,
                identifierKey: normalizeIdentifier(STR_GPU, String(index)),
                gpuIndex: index,
                value: buildDeviceSelectionValue(STR_GPU, index)
            };
        }
        throw new Error(`Missing identifier for ${resolvedType} selection`);
    }

    const [rawType, ...rest] = raw.split('::');
    const resolvedType = resolveSupportedHistoryComponent(lastSnapshot, supportedHistoryComponents, rawType);
    const decodedIdentifier = toTrimmedString(decodeURIComponent(rest.join('::')));
    if (!decodedIdentifier) {
        throw new Error(`Missing identifier for ${resolvedType} selection`);
    }
    const identifierKey = normalizeIdentifier(resolvedType, decodedIdentifier);
    if (!identifierKey) {
        throw new Error(`Missing identifier for ${resolvedType} selection`);
    }
    const gpuIndex = resolvedType === STR_GPU ? Number(identifierKey) || 0 : null;
    return {
        type: resolvedType,
        identifier: decodedIdentifier,
        identifierKey,
        gpuIndex,
        value: buildDeviceSelectionValue(resolvedType, identifierKey)
    };
};

const resolveGpuHistoryIndex = (target: DeviceSelection | null): number | null => {
    if (target?.type !== STR_GPU) return null;
    for (const candidate of [target.gpuIndex, target.identifier, target.identifierKey]) {
        const numeric = Number(candidate);
        if (Number.isFinite(numeric)) return Math.max(0, Math.floor(numeric));
    }
    return 0;
};

const metricSupportsDevice = (metricKey: JsonValue | null | undefined, component: JsonValue | null | undefined, metricConfig: MetricConfig): boolean => {
    const metricKeyString = String(metricKey);
    const config = metricConfig[metricKeyString];
    if (!config?.devices) return false;
    const normalized = normalizeHistoryComponent(toString(component));
    return config.devices.some((device) => normalizeHistoryComponent(device) === normalized);
};

const getDefaultMetricForDevice = (component: JsonValue | null | undefined, metricConfig: MetricConfig): string => {
    const normalized = normalizeHistoryComponent(toString(component));
    const preferred = {
        [STR_CPU]: STR_USAGE,
        [STR_GPU]: STR_USAGE,
        [STR_DISK]: 'disk_usage',
        [STR_NETWORK]: 'network_download'
    }[normalized];
    if (preferred && metricSupportsDevice(preferred, normalized, metricConfig)) return preferred;
    return Object.keys(metricConfig).find((metric) => metricSupportsDevice(metric, normalized, metricConfig)) || STR_USAGE;
};

const resolveMetricFromQuery = (component: JsonValue | null | undefined, candidate: JsonValue | null | undefined, metricConfig: MetricConfig): string | null => {
    const key = toTrimmedString(toString(candidate));
    return key && metricSupportsDevice(key, component, metricConfig) ? key : null;
};

const getSelectionFromQuery = <T>(router: T, metricConfig: MetricConfig): QuerySelection | null => {
    const provider = isRouterQueryParametersProvider(router) ? router : null;
    const raw = provider?.getQueryParameters?.() ?? null;
    const queryParameters = isStringRecordValue(raw) ? raw : {};
    const component = normalizeHistoryComponent(queryParameters['component']);
    if (!component) return null;
    let selectionValue: string;
    if (component === STR_GPU) {
        const index = Number(queryParameters['gpu_index']);
        if (!Number.isInteger(index) || index < 0) return null;
        selectionValue = buildDeviceSelectionValue(STR_GPU, index);
    } else if (component === STR_DISK || component === STR_NETWORK) {
        const identifier = toTrimmedString(queryParameters['identifier']);
        if (!identifier) return null;
        selectionValue = buildDeviceSelectionValue(component, identifier);
    } else {
        selectionValue = STR_CPU;
    }
    return {
        selectionValue,
        metric: resolveMetricFromQuery(component, queryParameters['metric'], metricConfig),
        component
    };
};

const areSameSelection = (selectionValue: JsonValue | null | undefined, selectedDevice: JsonValue | null | undefined, selectedMetric: JsonValue | null | undefined, preferredMetric: JsonValue | null | undefined, lastSnapshot: HardwareSnapshot | null | undefined, supportedHistoryComponents: string[] | undefined): boolean => {
    const parsed = parseDeviceSelection(selectedDevice, lastSnapshot, supportedHistoryComponents);
    return parsed.value === selectionValue && selectedMetric === preferredMetric;
};

export { areSameSelection, buildDeviceSelectionValue, getDefaultMetricForDevice, getSelectionFromQuery, isHistoryComponentSupported, metricSupportsDevice, parseDeviceSelection, resolveGpuHistoryIndex, resolveHistoryComponents, resolveMetricFromQuery, resolveSupportedHistoryComponent };
