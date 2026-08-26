/* SoAI - Metrics page widgets mapping [frontend/assets/ts/pages/metrics/widgets/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readRuntimeFiniteNumberOrFallbackValue } from '@core/types/numberCoercionReaders.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { toTrimmedLower, toTrimmedString } from '@core/normalize.ts';
import type { MetricsData } from '@pages/metrics/types.ts';

const readNamedMetricValue = (source: JsonValue | null | undefined, name: string): JsonValue | null => {
    if (!isJsonObject(source)) {
        return null;
    }
    if (name in source) {
        return source[name] ?? null;
    }
    const normalizedName = toTrimmedLower(name);
    if (!normalizedName) {
        return null;
    }
    for (const [key, value] of Object.entries(source)) {
        if (toTrimmedLower(key) === normalizedName) {
            return value;
        }
    }
    return null;
};

const resolvePluginName = (plugin: JsonObject): string => toTrimmedString(plugin['displayName']) || toTrimmedString(plugin['name']);

const resolvePluginRequestCount = (metrics: MetricsData | null, plugin: JsonObject): number => {
    const pluginName = resolvePluginName(plugin);
    if (!metrics || !pluginName || !isJsonObject(metrics.plugins)) {
        return 0;
    }
    const pluginMetrics = readNamedMetricValue(metrics.plugins, pluginName);
    if (!isJsonObject(pluginMetrics)) {
        return 0;
    }
    return readRuntimeFiniteNumberOrFallbackValue(pluginMetrics['requestsTotal'], 0);
};

const resolvePluginTokenCount = (metrics: MetricsData | null, plugin: JsonObject): number => {
    const pluginName = resolvePluginName(plugin);
    if (!metrics || !pluginName) {
        return 0;
    }
    const billedTokens = readRuntimeFiniteNumberOrFallbackValue(readNamedMetricValue(metrics.billing?.tokensByPlugin, pluginName), 0);
    if (billedTokens > 0) {
        return billedTokens;
    }
    const usageEntry = readNamedMetricValue(metrics.usage?.byPlugin, pluginName);
    if (!isJsonObject(usageEntry)) {
        return 0;
    }
    return readRuntimeFiniteNumberOrFallbackValue(usageEntry['textTokens'], 0);
};

export { resolvePluginName, resolvePluginRequestCount, resolvePluginTokenCount };
