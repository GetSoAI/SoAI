/* SoAI - Invisible streaming activity update fast path [frontend/assets/ts/features/chat/stream/streamActivityFastPath.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { INLINE_ACTIVITY_DETAILS_OPEN_REQUESTED_ATTRIBUTE } from '@features/chat/message/inlineActivityDetailsIdentity.ts';
import { INLINE_ACTIVITY_DETAILS_LOADING_ATTRIBUTE, INLINE_ACTIVITY_DETAILS_OPEN_PENDING_ATTRIBUTE } from '@features/chat/message/inlineActivityDetailsPendingState.ts';
import { resolveStreamActivityVisibleState, streamActivityVisibleStatesMatch } from '@features/chat/stream/streamActivityVisibleState.ts';
import type { RenderStreamingMessageContentArguments } from '@features/chat/stream/streamMessageRenderingContracts.ts';

const UNSAFE_INLINE_ACTIVITY_DETAILS_SELECTOR = `.inline-activity:is([data-collapsed="false"], [${INLINE_ACTIVITY_DETAILS_OPEN_PENDING_ATTRIBUTE}="true"], [${INLINE_ACTIVITY_DETAILS_OPEN_REQUESTED_ATTRIBUTE}="true"], [${INLINE_ACTIVITY_DETAILS_LOADING_ATTRIBUTE}="true"], [data-collapsing="true"])`;

const hasUnsafeInlineActivityDetailsState = (messageRoot: Element | null): boolean => {
    if (!(messageRoot instanceof HTMLElement)) {
        return true;
    }
    return dom.resolve(UNSAFE_INLINE_ACTIVITY_DETAILS_SELECTOR, messageRoot) instanceof HTMLElement;
};

const hasReusableStreamingStructure = (inputArguments: RenderStreamingMessageContentArguments, target: HTMLElement): boolean => {
    const streamSegments = inputArguments.cached.streamSegments;
    return inputArguments.cached.renderMode === 'streaming' && streamSegments instanceof HTMLElement && target.contains(streamSegments);
};

const shouldUseInvisibleTimelineActivityFastPath = (inputArguments: RenderStreamingMessageContentArguments, target: HTMLElement): boolean => {
    if (inputArguments.patchType !== 'timeline-activity') {
        return false;
    }
    if (!hasReusableStreamingStructure(inputArguments, target)) {
        return false;
    }
    if (hasUnsafeInlineActivityDetailsState(inputArguments.cached.messageRoot)) {
        return false;
    }
    return streamActivityVisibleStatesMatch(inputArguments.cached.lastAppliedActivityVisibleState, resolveStreamActivityVisibleState(inputArguments.message));
};

export { shouldUseInvisibleTimelineActivityFastPath };
