/* SoAI - Chat feature stream message render state [frontend/assets/ts/features/chat/stream/streamMessageRenderState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RenderStreamingMessageContentArguments } from '@features/chat/stream/streamMessageRenderingContracts.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { syncRunningActivitySummaryForMessageTextRoot, syncStreamingStatusPreviewAttributes } from '@features/chat/stream/streamMessagePassiveDomSync.ts';
import { resetTextTrackingState } from '@features/chat/stream/streamMessageStreamingStructure.ts';
import { resetStreamingActivityCacheState, type StreamingElementCache } from '@features/chat/stream/streamDomCache.ts';

const resetStreamingRenderCache = (cached: StreamingElementCache): void => {
    cached.lastRenderedAssistantRevision = null;
    resetTextTrackingState(cached);
    cached.activeStreamTextRunKey = null;
    cached.segmentMarkupByKey = null;
    cached.segmentSignatureByKey = null;
    cached.streamText = null;
    cached.streamTextSettled = null;
    cached.streamTextTail = null;
    cached.streamSegments = null;
    cached.textDeltaTimelineReference = null;
    cached.textDeltaTimelineScannedLength = 0;
    cached.textDeltaTimelineHasTextDelta = false;
    resetStreamingActivityCacheState(cached);
};

const syncStreamingMessagePassiveState = (inputArguments: { message: RenderStreamingMessageContentArguments['message']; target: HTMLElement; messageManager: RenderStreamingMessageContentArguments['messageManager']; cached?: StreamingElementCache | null }): boolean => {
    let updated = false;
    if (syncStreamingStatusPreviewAttributes(inputArguments.message, inputArguments.target, true)) {
        updated = true;
    }
    const summary = inputArguments.messageManager.resolveRunningActivitySummary(inputArguments.message, serverEpochMs());
    if (syncRunningActivitySummaryForMessageTextRoot(summary, inputArguments.target, inputArguments.cached ?? null)) {
        updated = true;
    }
    return updated;
};

const syncStreamingTextVisibility = (streamText: HTMLElement, visible: boolean): boolean => {
    const nextVisibility = visible ? 'true' : 'false';
    if (streamText.getAttribute('data-stream-text-visible') === nextVisibility) {
        return false;
    }
    streamText.setAttribute('data-stream-text-visible', nextVisibility);
    return true;
};

export { resetStreamingRenderCache, syncStreamingMessagePassiveState, syncStreamingTextVisibility };
