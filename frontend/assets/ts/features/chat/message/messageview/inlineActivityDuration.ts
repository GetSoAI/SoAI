/* SoAI - Chat feature inline activity duration [frontend/assets/ts/features/chat/message/messageview/inlineActivityDuration.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { formatStableElapsedDurationFromMs, resolveStableElapsedDurationReserveCharacters } from '@core/primitives/duration.ts';
import { CHAT_ACTIVITY_DURATION_REFRESH_INTERVAL_MS } from '@features/chat/chatConstants.ts';
import type { InlineLoadingActivitySegment, InlineProcessingActivitySegment, InlineThinkingActivitySegment, InlineToolActivitySegment, InlineWaitForUserActivitySegment } from '@features/chat/message/messageSegments.ts';
import type { ChatMessageRenderHost } from '@features/chat/message/messageview/types.ts';

interface InlineActivityDurationArguments {
    status: string;
    durationMs?: number | undefined;
    startedAtMs?: number | undefined;
    nowMs?: number | undefined;
}

type InlineDurationActivitySegment = InlineToolActivitySegment | InlineThinkingActivitySegment | InlineLoadingActivitySegment | InlineProcessingActivitySegment | InlineWaitForUserActivitySegment;

const INLINE_ACTIVITY_DURATION_RESERVE_PROPERTY = '--inline-activity-duration-reserve';

const resolveFiniteDurationMs = (durationMs: number | undefined): number | null => {
    if (typeof durationMs !== 'number' || !Number.isFinite(durationMs)) {
        return null;
    }
    return Math.max(0, Math.floor(durationMs));
};

const resolveInlineActivityRefreshIntervalMs = (durationMs: number): number => {
    void durationMs;
    return CHAT_ACTIVITY_DURATION_REFRESH_INTERVAL_MS;
};

const quantizeDurationMsToRefreshInterval = (durationMs: number, quantization: 'floor' | 'ceil'): number => {
    if (!Number.isFinite(durationMs)) {
        return 0;
    }
    const normalizedDurationMs = Math.max(0, durationMs);
    const intervalMs = resolveInlineActivityRefreshIntervalMs(normalizedDurationMs);
    if (!Number.isInteger(intervalMs) || intervalMs <= 0) {
        return Math.floor(normalizedDurationMs);
    }
    const buckets = quantization === 'ceil' ? Math.ceil(normalizedDurationMs / intervalMs) : Math.floor(normalizedDurationMs / intervalMs);
    const quantized = buckets * intervalMs;
    if (!Number.isFinite(quantized) || quantized < 0) {
        return 0;
    }
    return quantized;
};

const resolveInlineActivityDurationArguments = (segment: InlineDurationActivitySegment, nowMs?: number | undefined): InlineActivityDurationArguments => ({
    status: segment.status,
    durationMs: segment.durationMs,
    startedAtMs: segment.startedAtMs,
    nowMs
});

const resolveInlineActivityDisplayDurationMs = (inputArguments: InlineActivityDurationArguments): number | null => {
    if (inputArguments.status === 'pending') {
        return null;
    }
    const explicitDurationMs = resolveFiniteDurationMs(inputArguments.durationMs);
    if (inputArguments.status !== 'running') {
        return explicitDurationMs;
    }
    if (typeof inputArguments.startedAtMs !== 'number' || !Number.isFinite(inputArguments.startedAtMs) || inputArguments.startedAtMs < 0 || typeof inputArguments.nowMs !== 'number' || !Number.isFinite(inputArguments.nowMs)) {
        return explicitDurationMs;
    }
    const liveDurationMs = Math.max(0, Math.floor(inputArguments.nowMs - inputArguments.startedAtMs));
    return explicitDurationMs === null ? liveDurationMs : Math.max(explicitDurationMs, liveDurationMs);
};

const resolveInlineActivityRefreshDelayMs = (inputArguments: InlineActivityDurationArguments): number | null => {
    if (inputArguments.status !== 'running') {
        return null;
    }
    const displayDurationMs = resolveInlineActivityDisplayDurationMs(inputArguments);
    if (displayDurationMs === null) {
        return null;
    }
    return resolveInlineActivityRefreshIntervalMs(displayDurationMs);
};

const resolveInlineActivityLabelDurationMs = (inputArguments: InlineActivityDurationArguments): number | null => {
    const resolvedDurationMs = resolveInlineActivityDisplayDurationMs(inputArguments);
    if (resolvedDurationMs === null) {
        return null;
    }
    return inputArguments.status === 'running' ? quantizeDurationMsToRefreshInterval(resolvedDurationMs, 'floor') : resolvedDurationMs;
};

const resolveInlineActivityDurationLabel = (inputArguments: InlineActivityDurationArguments): string | null => {
    const labelDurationMs = resolveInlineActivityLabelDurationMs(inputArguments);
    if (labelDurationMs === null) {
        return null;
    }
    return formatStableElapsedDurationFromMs(labelDurationMs);
};

const resolveInlineActivityDurationReserveCharacters = (inputArguments: InlineActivityDurationArguments): number | null => {
    const labelDurationMs = resolveInlineActivityLabelDurationMs(inputArguments);
    if (labelDurationMs === null) {
        return null;
    }
    return resolveStableElapsedDurationReserveCharacters(labelDurationMs);
};

const formatInlineActivityDurationLabel = formatStableElapsedDurationFromMs;

const renderInlineActivityDurationReserveStyleAttribute = (reserveCharacters: number | null | undefined): string => {
    if (typeof reserveCharacters !== 'number' || !Number.isFinite(reserveCharacters) || reserveCharacters <= 0) {
        return '';
    }
    return ` style="${INLINE_ACTIVITY_DURATION_RESERVE_PROPERTY}:${String(Math.floor(reserveCharacters))}"`;
};

const renderInlineActivityDurationMarkup = (escapeHtml: (value: string) => string, label: string, options?: { extraAttributes?: string; reserveCharacters?: number | null }): string => {
    const extraAttributes = options?.extraAttributes ?? '';
    const reserveStyle = renderInlineActivityDurationReserveStyleAttribute(options?.reserveCharacters);
    return `<span class="inline-activity-duration"${extraAttributes}${reserveStyle}>${escapeHtml(label)}</span>`;
};

const renderInlineActivityDuration = (host: ChatMessageRenderHost, inputArguments: InlineActivityDurationArguments): string => {
    const label = resolveInlineActivityDurationLabel(inputArguments);
    if (label === null) {
        return '';
    }
    return renderInlineActivityDurationMarkup((value) => host.escapeHtml(value), label, {
        reserveCharacters: resolveInlineActivityDurationReserveCharacters(inputArguments)
    });
};

export { INLINE_ACTIVITY_DURATION_RESERVE_PROPERTY, formatInlineActivityDurationLabel, quantizeDurationMsToRefreshInterval, renderInlineActivityDuration, renderInlineActivityDurationMarkup, resolveInlineActivityDisplayDurationMs, resolveInlineActivityDurationArguments, resolveInlineActivityRefreshDelayMs, resolveInlineActivityDurationLabel, resolveInlineActivityDurationReserveCharacters };
export type { InlineActivityDurationArguments };
