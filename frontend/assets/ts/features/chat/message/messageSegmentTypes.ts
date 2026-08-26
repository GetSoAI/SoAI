/* SoAI - Chat feature message segment types [frontend/assets/ts/features/chat/message/messageSegmentTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { InlineActionUpdateSegment, InlineLoadingActivitySegment, InlineProcessingActivitySegment, InlineThinkingActivitySegment, InlineToolActivitySegment, InlineWaitForUserActivitySegment, MessageSegment } from '@features/chat/message/messageSegments.ts';
import { isInlineStatusActivitySegment } from '@features/chat/message/inlineStatusActivityIdentity.ts';

type InlineRefreshActivitySegment = InlineToolActivitySegment | InlineThinkingActivitySegment | InlineLoadingActivitySegment | InlineProcessingActivitySegment | InlineWaitForUserActivitySegment;
type InlineDetailsSegment = InlineToolActivitySegment | InlineThinkingActivitySegment;
type InlineStatusActivitySegment = InlineLoadingActivitySegment | InlineProcessingActivitySegment | InlineWaitForUserActivitySegment;
type InlineTimelineSequenceSegment = InlineActionUpdateSegment | InlineThinkingActivitySegment;

const isInlineRefreshActivitySegment = (segment: MessageSegment): segment is InlineRefreshActivitySegment => {
    return segment.type === 'inline_tool_activity' || segment.type === 'inline_thinking_activity' || segment.type === 'inline_loading_activity' || segment.type === 'inline_processing_activity' || segment.type === 'inline_wait_for_user_activity';
};

const isInlineDetailsSegment = (segment: MessageSegment): segment is InlineDetailsSegment => {
    return segment.type === 'inline_tool_activity' || segment.type === 'inline_thinking_activity';
};

const isInlineTimelineSequenceSegment = (segment: MessageSegment): segment is InlineTimelineSequenceSegment => {
    return segment.type === 'inline_action_update' || segment.type === 'inline_thinking_activity';
};

const isThinkingRenderSegment = (segment: MessageSegment): boolean => {
    return isInlineTimelineSequenceSegment(segment);
};

export { isInlineDetailsSegment, isInlineRefreshActivitySegment, isInlineStatusActivitySegment, isInlineTimelineSequenceSegment, isThinkingRenderSegment };
export type { InlineDetailsSegment, InlineRefreshActivitySegment, InlineStatusActivitySegment, InlineTimelineSequenceSegment };
