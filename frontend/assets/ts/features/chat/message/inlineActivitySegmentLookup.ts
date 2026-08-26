/* SoAI - Chat feature inline activity segment lookup [frontend/assets/ts/features/chat/message/inlineActivitySegmentLookup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { InlineThinkingActivitySegment, InlineToolActivitySegment, MessageSegment } from '@features/chat/message/messageSegments.ts';
import { resolveSubagentToolResultModel } from '@features/chat/message/messageview/subagentStreamSegments.ts';
import { isSubagentChildToolCallId } from '@features/chat/message/messageview/subagentToolCallSegments.ts';
import { normalizeToolLeafName } from '@features/chat/toolactivity/toolLeafName.ts';
import { resolveAssistantVariantIdentity } from '@core/chat/assistantIdentity.ts';

const hasSubagentStreamPayload = (payload: JsonValue | undefined): payload is JsonValue => {
    if (!isJsonObject(payload)) {
        return false;
    }
    return isJsonObject(payload['subagent']) && isJsonObject(payload['subagentStream']);
};

type InlineActivityLookupType = 'inline_tool_activity' | 'inline_thinking_activity';
type InlineActivityLookupSegment = InlineToolActivitySegment | InlineThinkingActivitySegment;

const resolveSubagentChildSegments = (segment: InlineToolActivitySegment): MessageSegment[] => {
    if (normalizeToolLeafName(segment.toolName) !== 'subagent_spawn') {
        return [];
    }
    if (!hasSubagentStreamPayload(segment.result)) {
        return [];
    }
    const assistantIdentity = resolveAssistantVariantIdentity({
        assistantTurnTimestamp: segment.assistantTurnAtMs,
        modelVariantIndex: segment.modelVariantIndex
    });
    if (assistantIdentity === null) {
        throw new Error(`Inline activity details segment missing assistant comparison identity for ${segment.callId}.`);
    }
    const model = resolveSubagentToolResultModel(segment.result, segment.callId, {
        assistantTurnTimestamp: assistantIdentity.assistantTurnTimestamp,
        modelVariantIndex: assistantIdentity.modelVariantIndex
    });
    return model.streamSegments;
};

const segmentMatchesTimelineSequence = (segment: InlineActivityLookupSegment, timelineSequenceIndex: number | null): boolean => {
    if (timelineSequenceIndex === null) {
        return true;
    }
    if (segment.type !== 'inline_thinking_activity') {
        return true;
    }
    return segment.timelineSequenceIndex === timelineSequenceIndex;
};

const findInlineActivitySegment = (segments: MessageSegment[], expectedType: InlineActivityLookupType, callId: string, timelineSequenceIndex: number | null = null): InlineActivityLookupSegment | null => {
    for (const segment of segments) {
        if (!segment) {
            continue;
        }
        if ((segment.type === 'inline_tool_activity' || segment.type === 'inline_thinking_activity') && segment.type === expectedType && segment.callId === callId && segmentMatchesTimelineSequence(segment, timelineSequenceIndex)) {
            return segment;
        }
    }
    if (expectedType !== 'inline_tool_activity' || !isSubagentChildToolCallId(callId)) {
        return null;
    }
    for (const segment of segments) {
        if (!segment) {
            continue;
        }
        if (segment.type === 'inline_tool_activity') {
            const nested = findInlineActivitySegment(resolveSubagentChildSegments(segment), expectedType, callId, timelineSequenceIndex);
            if (nested !== null) {
                return nested;
            }
        }
    }
    return null;
};

export { findInlineActivitySegment };
export type { InlineActivityLookupType, InlineActivityLookupSegment };
