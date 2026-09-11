/* SoAI - Chat feature collapsed loading summary rendering [frontend/assets/ts/features/chat/message/messageview/collapsedLoadingSummaryRendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveLatestLoadingActivityFromMessage } from '@features/chat/assistanteventtimeline/activityState.ts';
import { resolveTimelineSegmentKey } from '@features/chat/message/messageTimelineSegmentKeys.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { resolveLoadingActivityToggleEnabled } from '@features/chat/message/messageview/loadingActivityToggleEnabled.ts';
import { COLLAPSED_LOADING_CONTENT_WRAPPER_ATTRIBUTE } from '@features/chat/message/messageview/loadingActivityCollapsePolicy.ts';
import { isInlineRefreshActivitySegment, isInlineTimelineSequenceSegment } from '@features/chat/message/messageSegmentTypes.ts';
import type { InlineLoadingActivitySegment, MessageSegment } from '@features/chat/message/messageSegments.ts';
import type { ChatMessageRenderPresentation } from '@features/chat/message/messageRenderPresentation.ts';

type InlineLoadingActivityStatus = InlineLoadingActivitySegment['status'];
type CollapsedLoadingStreamingPhase = {
    displayStatus: InlineLoadingActivityStatus;
    includeRunningLiveDuration: boolean;
};

interface CollapsedLoadingSummaryDependencies {
    nowMs: () => number;
    renderTimelineSegmentsMarkup: (segments: MessageSegment[]) => string;
    renderAssistantBodyItem: (markup: string, key: string, signature: string) => string;
    renderLoadingActivityGroup: (segment: InlineLoadingActivitySegment, inputArguments: { displayStatus: InlineLoadingActivityStatus; durationStatus?: InlineLoadingActivityStatus; toggleEnabled: boolean }) => string;
}

const isCollapsedActivitySegment = (segment: MessageSegment): boolean => {
    return isInlineRefreshActivitySegment(segment) || isInlineTimelineSequenceSegment(segment);
};

const resolveNonNegativeDurationMs = (value: number | undefined): number | null => {
    if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) {
        return null;
    }
    return Math.floor(value);
};

const resolveLoadingSegment = (segments: MessageSegment[]): { index: number; segment: InlineLoadingActivitySegment | null } => {
    const index = segments.findIndex((segment): segment is InlineLoadingActivitySegment => segment.type === 'inline_loading_activity');
    if (index < 0) {
        return { index, segment: null };
    }
    const segment = segments[index];
    if (!segment || segment.type !== 'inline_loading_activity') {
        return { index: -1, segment: null };
    }
    return { index, segment };
};

const resolveCollapsedLoadingStreamingPhase = (segments: MessageSegment[]): CollapsedLoadingStreamingPhase => {
    for (let index = segments.length - 1; index >= 0; index -= 1) {
        const segment = segments[index];
        if (!segment) {
            continue;
        }
        if (segment.type === 'text' && segment.isStreamingActive === true) {
            return {
                displayStatus: 'completed',
                includeRunningLiveDuration: false
            };
        }
        if (isCollapsedActivitySegment(segment)) {
            return {
                displayStatus: 'running',
                includeRunningLiveDuration: true
            };
        }
    }
    return {
        displayStatus: 'running',
        includeRunningLiveDuration: true
    };
};

const resolveCollapsedActivityDurationMs = (segment: MessageSegment, nowMs: number, includeRunningLiveDuration: boolean, durationOverrideMs: number | undefined = undefined): number | null => {
    if (!isInlineRefreshActivitySegment(segment)) {
        return null;
    }
    const durationMs = resolveNonNegativeDurationMs(segment.durationMs);
    const explicitDurationMs = resolveNonNegativeDurationMs(durationOverrideMs) ?? durationMs;
    if (segment.status !== 'running' || !includeRunningLiveDuration) {
        return explicitDurationMs;
    }
    const startedAtMs = resolveNonNegativeDurationMs(segment.startedAtMs);
    if (startedAtMs === null) {
        return explicitDurationMs;
    }
    const liveDurationMs = Math.max(0, Math.floor(nowMs - startedAtMs));
    return explicitDurationMs === null ? liveDurationMs : Math.max(explicitDurationMs, liveDurationMs);
};

const resolveCollapsedLoadingSummaryDurationMs = (segments: MessageSegment[], loadingIndex: number, latestLoadingActivityDurationMs: number | undefined, includeRunningLiveDuration: boolean, nowMs: number, initialDurationMs: number | null = null): number | null => {
    let totalDurationMs = initialDurationMs ?? 0;
    let hasDuration = initialDurationMs !== null;
    const firstActivityIndex = Math.max(0, loadingIndex);
    for (let index = firstActivityIndex; index < segments.length; index += 1) {
        const segment = segments[index];
        if (!segment || !isInlineRefreshActivitySegment(segment)) {
            continue;
        }
        const durationMs = resolveCollapsedActivityDurationMs(segment, nowMs, includeRunningLiveDuration, segment.type === 'inline_loading_activity' && index === loadingIndex ? latestLoadingActivityDurationMs : undefined);
        if (durationMs === null) {
            continue;
        }
        totalDurationMs += durationMs;
        hasDuration = true;
    }
    return hasDuration ? totalDurationMs : null;
};

const applyCollapsedLoadingSummaryDuration = (segment: InlineLoadingActivitySegment, durationMs: number | null): InlineLoadingActivitySegment => {
    if (durationMs === null) {
        return segment;
    }
    return {
        ...segment,
        durationMs: durationMs
    };
};

const applyCollapsedLoadingPresentationTiming = (segment: InlineLoadingActivitySegment, displayStatus: InlineLoadingActivityStatus, nowMs: number): InlineLoadingActivitySegment => {
    const durationMs = resolveNonNegativeDurationMs(segment.durationMs);
    if (displayStatus !== 'running' || durationMs === null) {
        return segment;
    }
    return {
        ...segment,
        startedAtMs: Math.max(0, Math.floor(nowMs - durationMs))
    };
};

const resolveCollapsedLoadingSummarySegment = (message: ChatMessage, segments: MessageSegment[], includeRunningLiveDuration: boolean, nowMs: number): InlineLoadingActivitySegment | null => {
    const loadingResolution = resolveLoadingSegment(segments);
    const latestLoadingActivity = resolveLatestLoadingActivityFromMessage(message);
    if (loadingResolution.segment !== null) {
        const summaryDurationMs = resolveCollapsedLoadingSummaryDurationMs(segments, loadingResolution.index, latestLoadingActivity?.durationMs, includeRunningLiveDuration, nowMs);
        return applyCollapsedLoadingSummaryDuration(loadingResolution.segment, summaryDurationMs);
    }
    if (latestLoadingActivity === null) {
        return null;
    }
    const initialDurationMs = resolveNonNegativeDurationMs(latestLoadingActivity.durationMs);
    const summaryDurationMs = resolveCollapsedLoadingSummaryDurationMs(segments, 0, undefined, includeRunningLiveDuration, nowMs, initialDurationMs);
    const base: InlineLoadingActivitySegment = {
        type: 'inline_loading_activity',
        status: latestLoadingActivity.status,
        startedAtMs: latestLoadingActivity.startedAtMs,
        durationMs: summaryDurationMs ?? latestLoadingActivity.durationMs
    };
    const reason = latestLoadingActivity.reason;
    const errorType = latestLoadingActivity.errorType;
    return {
        ...base,
        ...(typeof reason === 'string' && reason ? { reason } : {}),
        ...(typeof errorType === 'string' && errorType ? { errorType: errorType } : {})
    };
};

const resolveCollapsedLoadingContentSegments = (segments: MessageSegment[]): MessageSegment[] => {
    const contentSegments: MessageSegment[] = [];
    let skippedLoadingSegment = false;
    for (const segment of segments) {
        if (!segment) {
            continue;
        }
        if (segment.type === 'inline_loading_activity' && skippedLoadingSegment === false) {
            skippedLoadingSegment = true;
            continue;
        }
        if (isCollapsedActivitySegment(segment)) {
            continue;
        }
        contentSegments.push(segment);
    }
    return contentSegments;
};

const renderCollapsedLoadingSummary = (dependencies: CollapsedLoadingSummaryDependencies, message: ChatMessage, segments: MessageSegment[], presentation: ChatMessageRenderPresentation): string => {
    const streamingPhase = presentation.isActiveStreamingAssistant ? resolveCollapsedLoadingStreamingPhase(segments) : null;
    const nowMs = dependencies.nowMs();
    const loadingSegment = resolveCollapsedLoadingSummarySegment(message, segments, streamingPhase?.includeRunningLiveDuration ?? false, nowMs);
    if (loadingSegment === null) {
        return dependencies.renderTimelineSegmentsMarkup(segments.filter((segment) => !isCollapsedActivitySegment(segment)));
    }
    const originalLoading = resolveLoadingSegment(segments);
    const loadingKey = resolveTimelineSegmentKey(originalLoading.segment ?? loadingSegment, Math.max(originalLoading.index, 0), new Map<string, number>());
    const displayStatus = streamingPhase?.displayStatus ?? loadingSegment.status;
    const displaySegment = applyCollapsedLoadingPresentationTiming(loadingSegment, displayStatus, nowMs);
    const loadingMarkup = dependencies.renderLoadingActivityGroup(displaySegment, {
        displayStatus,
        durationStatus: displayStatus === 'running' ? 'running' : displayStatus,
        toggleEnabled: resolveLoadingActivityToggleEnabled(segments)
    });
    const contentSegments = resolveCollapsedLoadingContentSegments(segments);
    const loadingHtml = dependencies.renderAssistantBodyItem(loadingMarkup, loadingKey, loadingMarkup);
    const contentHtml = dependencies.renderTimelineSegmentsMarkup(contentSegments);
    const collapsedContent = dependencies.renderAssistantBodyItem(`<div ${COLLAPSED_LOADING_CONTENT_WRAPPER_ATTRIBUTE}>${contentHtml}</div>`, 'collapsed_loading_content:1', contentHtml);
    return `${loadingHtml}${collapsedContent}`;
};

export { renderCollapsedLoadingSummary, resolveCollapsedLoadingContentSegments };
export type { CollapsedLoadingSummaryDependencies };
