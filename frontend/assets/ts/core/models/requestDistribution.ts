/* SoAI - Shared models request distribution [frontend/assets/ts/core/models/requestDistribution.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHART_COLOR_COUNT } from '@core/ui/chartColors.ts';
import { readRuntimeFiniteNumberOrFallbackValue } from '@core/types/numberCoercionReaders.ts';
import { isJsonArray, isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

type RequestDistributionSource = 'model' | 'plugin' | 'apiKey' | 'token';

interface RequestDistributionEntry {
    key: string;
    label: string;
    value: number;
    ratio: number;
    swatchIndex: number;
}

interface RequestDistributionSlice {
    key: string;
    swatchIndex: number;
    startAngle: number;
    endAngle: number;
}

interface RequestDistributionDataset {
    entries: RequestDistributionEntry[];
    slices: RequestDistributionSlice[];
}

interface RequestDistributionInput {
    key: string;
    label: string;
    value: number;
}

const resolveModelDistributionLabel = (key: string): string => key.split('/').pop() ?? key;

const readPositiveRequestTotal = (value: JsonValue | undefined): number | null => {
    const total = readRuntimeFiniteNumberOrFallbackValue(value, null);
    return total !== null && total > 0 ? total : null;
};

const collectRequestDistributionEntries = (items: readonly RequestDistributionInput[]): RequestDistributionEntry[] => {
    const totals = [...items].sort((left, right) => right.value - left.value);
    const total = totals.reduce((sum, entry) => sum + entry.value, 0);
    if (total <= 0) {
        return [];
    }

    return totals.map((entry, index) => ({
        key: entry.key,
        label: entry.label,
        value: entry.value,
        ratio: entry.value / total,
        swatchIndex: index % CHART_COLOR_COUNT
    }));
};

const collectRequestDistributionMapInputs = (source: JsonValue | undefined, labelResolver: (key: string) => string): RequestDistributionInput[] => {
    if (!isJsonObject(source)) {
        return [];
    }
    const inputs: RequestDistributionInput[] = [];
    for (const [key, value] of Object.entries(source)) {
        const total = readPositiveRequestTotal(value);
        if (total === null) {
            continue;
        }
        inputs.push({ key, label: labelResolver(key), value: total });
    }
    return inputs;
};

const resolvePluginDistributionLabel = (key: string, pluginMetrics: JsonObject): string => {
    const displayName = pluginMetrics['displayName'];
    if (typeof displayName === 'string' && displayName.trim()) {
        return displayName.trim();
    }
    const name = pluginMetrics['name'];
    if (typeof name === 'string' && name.trim()) {
        return name.trim();
    }
    return key;
};

const collectPluginRequestDistributionInputs = (plugins: JsonValue | undefined): RequestDistributionInput[] => {
    if (!isJsonObject(plugins)) {
        return [];
    }
    const inputs: RequestDistributionInput[] = [];
    for (const [key, value] of Object.entries(plugins)) {
        if (!isJsonObject(value)) {
            continue;
        }
        const total = readPositiveRequestTotal(value['requestsTotal']);
        if (total === null) {
            continue;
        }
        inputs.push({ key, label: resolvePluginDistributionLabel(key, value), value: total });
    }
    return inputs;
};

const resolveApiKeyDistributionRows = (source: JsonValue | undefined): readonly JsonValue[] => {
    if (isJsonArray(source)) {
        return source;
    }
    if (!isJsonObject(source)) {
        return [];
    }
    const keys = source['keys'];
    return isJsonArray(keys) ? keys : [];
};

const resolveApiKeyDistributionLabel = (row: JsonObject, key: string): string => {
    const label = row['label'];
    if (typeof label === 'string' && label.trim()) {
        return label.trim();
    }
    const prefix = row['prefix'];
    if (typeof prefix === 'string' && prefix.trim()) {
        return prefix.trim();
    }
    return key;
};

const collectApiKeyRequestDistributionInputs = (apiKeys: JsonValue | undefined): RequestDistributionInput[] => {
    const inputs: RequestDistributionInput[] = [];
    for (const [index, value] of resolveApiKeyDistributionRows(apiKeys).entries()) {
        if (!isJsonObject(value)) {
            continue;
        }
        const total = readPositiveRequestTotal(value['request_count']);
        if (total === null) {
            continue;
        }
        const keyId = value['key_id'];
        const prefix = value['prefix'];
        const key = typeof keyId === 'string' && keyId.trim() ? keyId.trim() : typeof prefix === 'string' && prefix.trim() ? prefix.trim() : `api-key-${String(index)}`;
        inputs.push({ key, label: resolveApiKeyDistributionLabel(value, key), value: total });
    }
    return inputs;
};

const buildRequestDistributionSlices = (entries: readonly RequestDistributionEntry[]): RequestDistributionSlice[] => {
    let currentAngle = -Math.PI / 2;
    return entries.map((entry) => {
        const startAngle = currentAngle;
        const endAngle = currentAngle + entry.ratio * 2 * Math.PI;
        currentAngle = endAngle;
        return {
            key: entry.key,
            swatchIndex: entry.swatchIndex,
            startAngle,
            endAngle
        };
    });
};

const buildRequestDistributionDatasetFromInputs = (items: readonly RequestDistributionInput[]): RequestDistributionDataset => {
    const entries = collectRequestDistributionEntries(items);
    return {
        entries,
        slices: buildRequestDistributionSlices(entries)
    };
};

const buildModelRequestDistributionDataset = (requestsByModel: JsonValue | undefined, requestsByVirtualModel: JsonValue | undefined): RequestDistributionDataset => {
    const requestTotals = new Map<string, number>();
    for (const input of [...collectRequestDistributionMapInputs(requestsByModel, resolveModelDistributionLabel), ...collectRequestDistributionMapInputs(requestsByVirtualModel, resolveModelDistributionLabel)]) {
        requestTotals.set(input.key, (requestTotals.get(input.key) ?? 0) + input.value);
    }
    const inputs = Array.from(requestTotals.entries()).map(([key, value]) => ({ key, label: resolveModelDistributionLabel(key), value }));
    return buildRequestDistributionDatasetFromInputs(inputs);
};

const buildPluginRequestDistributionDataset = (plugins: JsonValue | undefined): RequestDistributionDataset => buildRequestDistributionDatasetFromInputs(collectPluginRequestDistributionInputs(plugins));
const buildApiKeyRequestDistributionDataset = (apiKeys: JsonValue | undefined): RequestDistributionDataset => buildRequestDistributionDatasetFromInputs(collectApiKeyRequestDistributionInputs(apiKeys));
const buildModelTokenDistributionDataset = (tokensByModel: JsonValue | undefined): RequestDistributionDataset => buildRequestDistributionDatasetFromInputs(collectRequestDistributionMapInputs(tokensByModel, resolveModelDistributionLabel));

export { buildApiKeyRequestDistributionDataset, buildModelRequestDistributionDataset, buildModelTokenDistributionDataset, buildPluginRequestDistributionDataset };
export type { RequestDistributionDataset, RequestDistributionEntry, RequestDistributionSlice, RequestDistributionSource };
