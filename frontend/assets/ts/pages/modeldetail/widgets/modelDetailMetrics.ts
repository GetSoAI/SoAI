/* SoAI - Model detail page widgets metrics [frontend/assets/ts/pages/modeldetail/widgets/modelDetailMetrics.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatInvariantNumber } from '@core/localization/public.ts';
import { resolveModelRequestCount } from '@core/models/usageMetrics.ts';
import { formatBytes } from '@core/primitives/byteSize.ts';
import { formatDuration } from '@core/primitives/duration.ts';
import { isFiniteNumber, isNumber, isString } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';

export interface ModelDetailMetricsHost {
    unwrapPayload(payload: JsonValue | null): JsonValue | null;
    setCurrentMetrics(payload: JsonObject): void;
    getModel(): ModelRecord | null;
    setInfo(id: string, value: JsonValue | null | undefined): void;
    getPluginKey(): string;
    updateTestPluginStatusDisplay(): void;
}

const resolvePluginMetrics = (pluginsPayload: JsonValue | undefined, pluginKey: string): JsonObject | null => {
    if (!isJsonObject(pluginsPayload)) {
        return null;
    }
    if (!isString(pluginKey) || !pluginKey) {
        return null;
    }
    const metrics = pluginsPayload[pluginKey];
    return isJsonObject(metrics) ? metrics : null;
};

const numberOrZero = (value: JsonValue | undefined): number => (isFiniteNumber(value) && value > 0 ? value : 0);

const formatAudioUsage = (seconds: number, bytes: number): string => {
    if (seconds > 0 && bytes > 0) {
        return `${formatDuration(seconds)} / ${formatBytes(bytes)}`;
    }
    if (seconds > 0) {
        return formatDuration(seconds);
    }
    return formatBytes(bytes);
};

const buildModelModalityUsageSummary = (usageByModel: JsonValue | undefined, modelId: string): string | null => {
    if (!isJsonObject(usageByModel)) {
        return null;
    }
    const modelUsage = usageByModel[modelId];
    if (!isJsonObject(modelUsage)) {
        return null;
    }
    const textTokens = numberOrZero(modelUsage['textTokens']);
    const audioInputBytes = numberOrZero(modelUsage['audioInputBytes']);
    const audioInputSeconds = numberOrZero(modelUsage['audioInputSeconds']);
    const audioOutputBytes = numberOrZero(modelUsage['audioOutputBytes']);
    const audioOutputSeconds = numberOrZero(modelUsage['audioOutputSeconds']);
    const imageInputCount = numberOrZero(modelUsage['imageInputCount']);
    const imageOutputCount = numberOrZero(modelUsage['imageOutputCount']);
    const parts: string[] = [];
    if (audioInputBytes > 0 || audioInputSeconds > 0) {
        const label = i18n.t('modelDetail.cards.metrics.audioIn');
        parts.push(`${label}: ${formatAudioUsage(audioInputSeconds, audioInputBytes)}`);
    }
    if (audioOutputBytes > 0 || audioOutputSeconds > 0) {
        const label = i18n.t('modelDetail.cards.metrics.audioOut');
        parts.push(`${label}: ${formatAudioUsage(audioOutputSeconds, audioOutputBytes)}`);
    }
    if (imageInputCount > 0) {
        const label = i18n.t('modelDetail.cards.metrics.imagesIn');
        parts.push(`${label}: ${i18n.formatNumber(imageInputCount)}`);
    }
    if (imageOutputCount > 0) {
        const label = i18n.t('modelDetail.cards.metrics.imagesOut');
        parts.push(`${label}: ${i18n.formatNumber(imageOutputCount)}`);
    }
    if (textTokens > 0) {
        const label = i18n.t('modelDetail.cards.metrics.textTokens');
        parts.push(`${label}: ${i18n.formatNumber(textTokens)}`);
    }
    return parts.length ? parts.join(' | ') : null;
};

export const applyModelDetailMetricsUpdate = (host: ModelDetailMetricsHost, data: JsonValue | null): void => {
    const payload = host.unwrapPayload(data);
    if (!isJsonObject(payload)) {
        return;
    }
    host.setCurrentMetrics(payload);

    const director = isJsonObject(payload['director']) ? payload['director'] : null;
    const billing = isJsonObject(payload['billing']) ? payload['billing'] : null;
    const usage = isJsonObject(payload['usage']) ? payload['usage'] : null;

    const model = host.getModel();
    if (model) {
        const count = resolveModelRequestCount(payload, model);
        host.setInfo('modeldetail-total-requests', i18n.formatNumber(count));
    }

    const tokensByModel = billing && isJsonObject(billing['tokensByModel']) ? billing['tokensByModel'] : null;
    if (tokensByModel && model && isString(model.universalId) && model.universalId) {
        const rawTokens = tokensByModel[model.universalId];
        const tokens = isNumber(rawTokens) ? rawTokens : 0;
        host.setInfo('modeldetail-tokens-generated', i18n.formatNumber(tokens));
    }

    const usageByModel = usage && isJsonObject(usage['byModel']) ? usage['byModel'] : null;
    if (model && isString(model.universalId) && model.universalId) {
        const usageSummary = usageByModel ? buildModelModalityUsageSummary(usageByModel, model.universalId) : null;
        host.setInfo('modeldetail-modality-usage', usageSummary);
    }

    const pluginMetrics = resolvePluginMetrics(payload['plugins'], host.getPluginKey());
    const pluginMetricsRecord = isJsonObject(pluginMetrics) ? pluginMetrics : null;
    const timings = pluginMetricsRecord && isJsonObject(pluginMetricsRecord['timings']) ? pluginMetricsRecord['timings'] : null;
    const latencyStats = timings && isJsonObject(timings['requestLatencyMsStats']) ? timings['requestLatencyMsStats'] : null;
    const latencyP95 = latencyStats ? latencyStats['p95'] : null;
    if (isNumber(latencyP95)) {
        host.setInfo('modeldetail-avg-latency', `${formatInvariantNumber(latencyP95, { maximumFractionDigits: 0 })}ms`);
    }

    const requestsFailed = pluginMetricsRecord ? pluginMetricsRecord['requestsFailed'] : null;
    if (isNumber(requestsFailed)) {
        host.setInfo('modeldetail-failed-requests', i18n.formatNumber(requestsFailed));
    }

    const directorTimings = director && isJsonObject(director['timings']) ? director['timings'] : null;
    const waitStats = directorTimings && isJsonObject(directorTimings['requestWaitTimeMsStats']) ? directorTimings['requestWaitTimeMsStats'] : null;
    const waitAvg = waitStats ? waitStats['avg'] : null;
    if (isNumber(waitAvg)) {
        host.setInfo('modeldetail-wait-time', `${formatInvariantNumber(waitAvg, { maximumFractionDigits: 0 })}ms`);
    }

    host.updateTestPluginStatusDisplay();
};
