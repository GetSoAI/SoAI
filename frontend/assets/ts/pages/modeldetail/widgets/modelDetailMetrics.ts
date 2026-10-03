/* SoAI - Model detail page widgets metrics [frontend/assets/ts/pages/modeldetail/widgets/modelDetailMetrics.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isolateLtrText } from '@core/localization/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { resolveModelRequestCount, resolveModelTokenCount } from '@core/models/usageMetrics.ts';
import { formatBytes } from '@core/primitives/byteSize.ts';
import { formatDuration } from '@core/primitives/duration.ts';
import { isFiniteNumber, isString } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';

export interface ModelDetailMetricsHost {
    unwrapPayload(payload: JsonValue | null): JsonValue | null;
    setCurrentMetrics(payload: JsonObject): void;
    getModel(): ModelRecord | null;
    setInfo(id: string, value: JsonValue | null | undefined): void;
    updateTestPluginStatusDisplay(): void;
}

const numberOrZero = (value: JsonValue | undefined): number => (isFiniteNumber(value) && value > 0 ? value : 0);

const formatAudioUsage = (seconds: number, bytes: number): string => {
    if (seconds > 0 && bytes > 0) {
        return `${formatDuration(seconds)} / ${isolateLtrText(formatBytes(bytes))}`;
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

    const usage = isJsonObject(payload['usage']) ? payload['usage'] : null;

    const model = host.getModel();
    if (model) {
        const count = resolveModelRequestCount(payload, model);
        host.setInfo('modeldetail-total-requests', i18n.formatNumber(count));
    }
    const universalId = model && isString(model.universalId) && model.universalId ? model.universalId : null;
    host.setInfo('modeldetail-tokens-generated', model && universalId ? i18n.formatNumber(resolveModelTokenCount(payload, model)) : null);

    if (universalId) {
        const usageByModel = usage && isJsonObject(usage['byModel']) ? usage['byModel'] : null;
        host.setInfo('modeldetail-modality-usage', usageByModel ? buildModelModalityUsageSummary(usageByModel, universalId) : null);
    }

    host.updateTestPluginStatusDisplay();
};
