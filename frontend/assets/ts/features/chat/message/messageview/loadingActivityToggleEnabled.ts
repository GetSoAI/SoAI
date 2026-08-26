/* SoAI - Chat feature loading activity toggle enabled [frontend/assets/ts/features/chat/message/messageview/loadingActivityToggleEnabled.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { MessageSegment } from '@features/chat/message/messageSegments.ts';

const resolveLoadingActivityToggleEnabled = (segments: MessageSegment[]): boolean => {
    let skippedLoadingSegment = false;
    for (const segment of segments) {
        if (!segment) {
            continue;
        }
        if (segment.type === 'inline_loading_activity' && skippedLoadingSegment === false) {
            skippedLoadingSegment = true;
            continue;
        }
        if (skippedLoadingSegment === false) {
            continue;
        }
        if (segment.type === 'inline_tool_activity' || segment.type === 'inline_thinking_activity' || segment.type === 'inline_action_update' || segment.type === 'inline_processing_activity' || segment.type === 'inline_wait_for_user_activity') {
            return true;
        }
    }
    return false;
};

const createLoadingActivityToggleSegmentResolver = (enabled: boolean): ((segment: MessageSegment) => boolean) => {
    let loadingActivityToggleConsumed = false;
    return (segment: MessageSegment): boolean => {
        if (segment.type !== 'inline_loading_activity') {
            return false;
        }
        const segmentEnabled = enabled && loadingActivityToggleConsumed === false;
        loadingActivityToggleConsumed = true;
        return segmentEnabled;
    };
};

export { createLoadingActivityToggleSegmentResolver, resolveLoadingActivityToggleEnabled };
