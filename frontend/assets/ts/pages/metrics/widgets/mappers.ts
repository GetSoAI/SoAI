/* SoAI - Metrics page widgets mapping [frontend/assets/ts/pages/metrics/widgets/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readRuntimeFiniteNumberOrFallbackValue } from '@core/types/numberCoercionReaders.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { toTrimmedLower, toTrimmedString } from '@core/normalize.ts';
import type { MetricsData } from '@pages/metrics/types.ts';

interface PluginMetricLookup {
    readMap(source: JsonValue | undefined): JsonObject | null;
    normalizedNames: Map<JsonObject, Map<string, JsonValue>>;
}

const createPluginMetricLookup = (): PluginMetricLookup => {
    const maps = new Map<JsonValue | undefined, JsonObject | null>();
    return {
        readMap: (source) => {
            const cached = maps.get(source);
            if (cached !== undefined) return cached;
            const record = isJsonObject(source) ? source : null;
            maps.set(source, record);
            return record;
        },
        normalizedNames: new Map()
    };
};

const readNamedMetricValue = (source: JsonValue | null | undefined, name: string, lookup?: PluginMetricLookup): JsonValue | null => {
    const record = lookup ? lookup.readMap(source) : isJsonObject(source) ? source : null;
    if (!record) {
        return null;
    }
    if (name in record) {
        return record[name] ?? null;
    }
    const normalizedName = toTrimmedLower(name);
    if (!normalizedName) {
        return null;
    }
    let normalizedNames = lookup?.normalizedNames.get(record);
    if (normalizedNames) return normalizedNames.get(normalizedName) ?? null;
    normalizedNames = lookup ? new Map<string, JsonValue>() : undefined;
    for (const [key, value] of Object.entries(record)) {
        const normalizedKey = toTrimmedLower(key);
        if (normalizedNames) {
            if (!normalizedNames.has(normalizedKey)) normalizedNames.set(normalizedKey, value);
        } else if (normalizedKey === normalizedName) {
            return value;
        }
    }
    if (normalizedNames) {
        lookup?.normalizedNames.set(record, normalizedNames);
        return normalizedNames.get(normalizedName) ?? null;
    }
    return null;
};

const resolvePluginName = (plugin: JsonObject): string => toTrimmedString(plugin['displayName']) || toTrimmedString(plugin['name']);

const resolvePluginRequestCount = (metrics: MetricsData | null, plugin: JsonObject, lookup?: PluginMetricLookup): number => {
    const pluginName = toTrimmedString(plugin['name']);
    if (!metrics || !pluginName || !(lookup ? lookup.readMap(metrics.plugins) : isJsonObject(metrics.plugins))) {
        return 0;
    }
    const pluginMetrics = readNamedMetricValue(metrics.plugins, pluginName, lookup);
    if (!isJsonObject(pluginMetrics)) {
        return 0;
    }
    return readRuntimeFiniteNumberOrFallbackValue(pluginMetrics['requestsTotal'], 0);
};

const resolvePluginTokenCount = (metrics: MetricsData | null, plugin: JsonObject, lookup?: PluginMetricLookup): number => {
    const pluginName = toTrimmedString(plugin['name']);
    if (!metrics || !pluginName) {
        return 0;
    }
    const billedTokens = readRuntimeFiniteNumberOrFallbackValue(readNamedMetricValue(metrics.billing?.tokensByPlugin, pluginName, lookup), 0);
    if (billedTokens > 0) {
        return billedTokens;
    }
    const usageEntry = readNamedMetricValue(metrics.usage?.byPlugin, pluginName, lookup);
    if (!isJsonObject(usageEntry)) {
        return 0;
    }
    return readRuntimeFiniteNumberOrFallbackValue(usageEntry['textTokens'], 0);
};

export { createPluginMetricLookup, resolvePluginName, resolvePluginRequestCount, resolvePluginTokenCount };
export type { PluginMetricLookup };
