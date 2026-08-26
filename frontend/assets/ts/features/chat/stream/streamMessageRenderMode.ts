/* SoAI - Chat feature stream message render mode [frontend/assets/ts/features/chat/stream/streamMessageRenderMode.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { isArray, isString } from '@core/typeGuards.ts';
import { resolveLatestLoadingActivityFromMessage } from '@features/chat/assistanteventtimeline/activityState.ts';
import { timelineHasAssistantTextDeltaEvent } from '@features/chat/assistanteventtimeline/timelineTextDeltas.ts';
import { COLLAPSED_LOADING_CONTENT_SELECTOR, COLLAPSED_LOADING_SUMMARY_SELECTOR, shouldCollapseLoadingActivities } from '@features/chat/message/messageview/loadingActivityCollapsePolicy.ts';
import { hasStreamSegments } from '@features/chat/stream/streamSegmentsMarker.ts';
import { extractPlainTextFromContentPart } from '@features/chat/stream/streamMessageTextDeltaPatching.ts';
import type { RenderStreamingMessageContentArguments } from '@features/chat/stream/streamMessageRenderingContracts.ts';
import type { StreamingElementCache } from '@features/chat/stream/streamDomCache.ts';

const isPassiveStreamRenderPatchType = (patchType: RenderStreamingMessageContentArguments['patchType']): boolean => patchType === 'passive-state' || patchType === 'none';

const messageHasAssistantTextDeltaTimeline = (message: RenderStreamingMessageContentArguments['message']): boolean => {
    return timelineHasAssistantTextDeltaEvent(message.assistantEventTimeline);
};

const cachedMessageHasAssistantTextDeltaTimeline = (message: RenderStreamingMessageContentArguments['message'], cached: StreamingElementCache): boolean => {
    const timeline = message.assistantEventTimeline;
    if (!isArray(timeline) || timeline.length === 0) {
        cached.textDeltaTimelineReference = null;
        cached.textDeltaTimelineScannedLength = 0;
        cached.textDeltaTimelineHasTextDelta = false;
        return false;
    }
    if (cached.textDeltaTimelineReference !== timeline || timeline.length < cached.textDeltaTimelineScannedLength) {
        cached.textDeltaTimelineReference = timeline;
        cached.textDeltaTimelineScannedLength = 0;
        cached.textDeltaTimelineHasTextDelta = false;
    }
    if (!cached.textDeltaTimelineHasTextDelta && timelineHasAssistantTextDeltaEvent(timeline, cached.textDeltaTimelineScannedLength)) {
        cached.textDeltaTimelineHasTextDelta = true;
    }
    cached.textDeltaTimelineReference = timeline;
    cached.textDeltaTimelineScannedLength = timeline.length;
    return cached.textDeltaTimelineHasTextDelta;
};

const streamMessageHasAssistantTextDeltaTimeline = (inputArguments: { message: RenderStreamingMessageContentArguments['message']; cached?: StreamingElementCache | null }): boolean => {
    if (inputArguments.cached !== null && inputArguments.cached !== undefined) {
        return cachedMessageHasAssistantTextDeltaTimeline(inputArguments.message, inputArguments.cached);
    }
    return messageHasAssistantTextDeltaTimeline(inputArguments.message);
};

const messageHasStreamText = (message: RenderStreamingMessageContentArguments['message']): boolean => {
    const content = message.content;
    if (isString(content)) {
        return content.length > 0;
    }
    if (!isArray(content) || content.length === 0) {
        return false;
    }
    for (const part of content) {
        if (extractPlainTextFromContentPart(part).length > 0) {
            return true;
        }
    }
    return false;
};

const shouldRenderCollapsedLoadingSummary = (message: RenderStreamingMessageContentArguments['message'], messageManager: RenderStreamingMessageContentArguments['messageManager']): boolean => {
    const loadingActivity = resolveLatestLoadingActivityFromMessage(message);
    if (loadingActivity === null) {
        return false;
    }
    return shouldCollapseLoadingActivities({
        isShowActivitiesEnabled: messageManager.isShowActivitiesEnabled(),
        collapsedOverride: messageManager.getLoadingActivityCollapsedState(message)
    });
};

const shouldSkipStreamingTextDeltaPatch = (inputArguments: { message: RenderStreamingMessageContentArguments['message']; patchType: RenderStreamingMessageContentArguments['patchType']; target: HTMLElement; cached?: StreamingElementCache | null }): boolean => {
    if (inputArguments.patchType !== 'text-delta') {
        return false;
    }
    if (streamMessageHasAssistantTextDeltaTimeline({ message: inputArguments.message, cached: inputArguments.cached ?? null })) {
        return false;
    }
    if (!messageHasStreamText(inputArguments.message)) {
        return true;
    }
    const timeline = inputArguments.message.assistantEventTimeline;
    if (!isArray(timeline) || timeline.length === 0) {
        return false;
    }
    return !hasStreamSegments(inputArguments.target);
};

const hasCollapsedLoadingStructure = (target: HTMLElement): boolean => {
    const summary = dom.resolve(COLLAPSED_LOADING_SUMMARY_SELECTOR, target);
    const content = dom.resolve(COLLAPSED_LOADING_CONTENT_SELECTOR, target);
    return summary instanceof HTMLElement && content instanceof HTMLElement;
};

export { hasCollapsedLoadingStructure, isPassiveStreamRenderPatchType, messageHasAssistantTextDeltaTimeline, messageHasStreamText, shouldRenderCollapsedLoadingSummary, shouldSkipStreamingTextDeltaPatch };
