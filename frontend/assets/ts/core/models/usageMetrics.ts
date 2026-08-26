/* SoAI - Shared models usage metrics [frontend/assets/ts/core/models/usageMetrics.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFiniteNumber, isString } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';

const extractMetricsRoot = (payload: JsonObject | null): JsonObject => {
    if (!isJsonObject(payload)) {
        throw new Error('Model usage metrics require an object payload');
    }
    const metrics = payload['metrics'];
    return isJsonObject(metrics) ? metrics : payload;
};

const requireMetricMap = (metricsPayload: JsonObject | null, key: string): JsonObject => {
    const root = extractMetricsRoot(metricsPayload);
    const director = root['director'];
    if (!isJsonObject(director)) {
        throw new Error('Model usage metrics require director metrics');
    }
    const metricMap = director[key];
    if (!isJsonObject(metricMap)) {
        throw new Error(`Model usage metrics require director.${key}`);
    }
    return metricMap;
};

const getBillingMetricMap = (metricsPayload: JsonObject | null, key: string): JsonObject | null => {
    const root = extractMetricsRoot(metricsPayload);
    const billing = root['billing'];
    if (!isJsonObject(billing)) {
        return null;
    }
    const metricMap = billing[key];
    return isJsonObject(metricMap) ? metricMap : null;
};

const resolveRealModelRequestMetricKey = (model: ModelRecord): string | null => {
    return isString(model.universalId) && model.universalId.trim() ? model.universalId.trim() : null;
};

const resolveVirtualModelRequestMetricKey = (model: ModelRecord): string | null => {
    return isString(model.name) && model.name.trim() ? model.name.trim() : null;
};

const resolveModelRequestCount = (metricsPayload: JsonObject | null, model: ModelRecord): number => {
    const isVirtual = model.type === 'virtual';
    const metricKey = isVirtual ? resolveVirtualModelRequestMetricKey(model) : resolveRealModelRequestMetricKey(model);
    if (!metricKey) {
        throw new Error('Model request metrics require a canonical model identifier');
    }
    const metricMap = requireMetricMap(metricsPayload, isVirtual ? 'requestsByVirtualModel' : 'requestsByModel');
    const count = metricMap[metricKey];
    return isFiniteNumber(count) ? count : 0;
};

const resolveModelTokenCount = (metricsPayload: JsonObject | null, model: ModelRecord): number => {
    const metricKey = resolveRealModelRequestMetricKey(model);
    if (!metricKey) {
        throw new Error('Model token metrics require a canonical model identifier');
    }
    const metricMap = getBillingMetricMap(metricsPayload, 'tokensByModel');
    if (!metricMap) {
        return 0;
    }
    const count = metricMap[metricKey];
    return isFiniteNumber(count) ? count : 0;
};

export { resolveModelRequestCount, resolveModelTokenCount };
