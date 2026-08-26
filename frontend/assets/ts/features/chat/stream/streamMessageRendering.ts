/* SoAI - Chat feature stream message rendering [frontend/assets/ts/features/chat/stream/streamMessageRendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { renderCollapsedLoadingMessageContent } from '@features/chat/stream/streamMessageCollapsedLoading.ts';
import { shouldUseInvisibleTimelineActivityFastPath } from '@features/chat/stream/streamActivityFastPath.ts';
import { shouldRenderCollapsedLoadingSummary, shouldSkipStreamingTextDeltaPatch } from '@features/chat/stream/streamMessageRenderMode.ts';
import { syncStreamingMessagePassiveState } from '@features/chat/stream/streamMessageRenderState.ts';
import type { RenderStreamingMessageContentArguments, RenderStreamingMessageContentResult } from '@features/chat/stream/streamMessageRenderingContracts.ts';
import { renderActiveStreamingMessageContent } from '@features/chat/stream/streamMessageStreamingContent.ts';

const renderStreamingMessageContent = (inputArguments: RenderStreamingMessageContentArguments): RenderStreamingMessageContentResult => {
    const target = inputArguments.cached.messageText;
    if (!(target instanceof HTMLElement)) {
        return {
            handled: false,
            invalidatedCache: true,
            updatedMarkup: false,
            target: null
        };
    }

    if (shouldRenderCollapsedLoadingSummary(inputArguments.message, inputArguments.messageManager)) {
        const result = renderCollapsedLoadingMessageContent(inputArguments, target);
        inputArguments.cached.lastRenderedAssistantRevision = result.handled && !result.invalidatedCache ? inputArguments.assistantRevision : null;
        return result;
    }

    if (shouldUseInvisibleTimelineActivityFastPath(inputArguments, target)) {
        const passiveUpdated = syncStreamingMessagePassiveState({ message: inputArguments.message, target, messageManager: inputArguments.messageManager, cached: inputArguments.cached });
        const result: RenderStreamingMessageContentResult = {
            handled: true,
            invalidatedCache: false,
            updatedMarkup: passiveUpdated,
            target
        };
        inputArguments.cached.lastRenderedAssistantRevision = inputArguments.assistantRevision;
        return result;
    }

    if (shouldSkipStreamingTextDeltaPatch({ message: inputArguments.message, patchType: inputArguments.patchType, target, cached: inputArguments.cached })) {
        const result: RenderStreamingMessageContentResult = {
            handled: true,
            invalidatedCache: false,
            updatedMarkup: syncStreamingMessagePassiveState({ message: inputArguments.message, target, messageManager: inputArguments.messageManager, cached: inputArguments.cached }),
            target
        };
        inputArguments.cached.lastRenderedAssistantRevision = inputArguments.assistantRevision;
        return result;
    }

    const result = renderActiveStreamingMessageContent(inputArguments, target);
    inputArguments.cached.lastRenderedAssistantRevision = result.handled && !result.invalidatedCache ? inputArguments.assistantRevision : null;
    return result;
};

export { renderStreamingMessageContent };
