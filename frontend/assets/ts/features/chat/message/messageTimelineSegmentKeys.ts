/* SoAI - Chat feature message timeline segment keys [frontend/assets/ts/features/chat/message/messageTimelineSegmentKeys.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { isNumber, isString } from '@core/typeGuards.ts';
import { isInlineStatusActivitySegment, resolveInlineStatusActivitySegmentBaseKey } from '@features/chat/message/inlineStatusActivityIdentity.ts';
import type { MessageSegment } from '@features/chat/message/messageSegments.ts';
import { isInlineTimelineSequenceSegment } from '@features/chat/message/messageSegmentTypes.ts';

const resolveTimelineSegmentBaseKey = (segment: MessageSegment, index: number): string => {
    if (segment.type === 'text' && isNumber(segment.timelineSequence)) {
        return `text:${String(segment.timelineSequence)}`;
    }
    if (isInlineStatusActivitySegment(segment)) {
        return resolveInlineStatusActivitySegmentBaseKey(segment, index);
    }
    if (isInlineTimelineSequenceSegment(segment)) {
        const callId = toTrimmedString(segment.callId);
        if (callId) {
            return `${segment.type}:${callId}:${String(segment.timelineSequenceIndex)}`;
        }
    }
    if ('callId' in segment) {
        const callIdValue = segment.callId;
        if (isString(callIdValue) && callIdValue.trim()) {
            return `${segment.type}:${callIdValue.trim()}`;
        }
    }
    if (segment.type === 'tool_call') {
        const rawId = segment.id;
        const rawName = segment.name;
        const suffix = isString(rawId) || typeof rawId === 'number' ? String(rawId) : isString(rawName) && rawName.trim() ? rawName.trim() : String(index);
        return `${segment.type}:${suffix}`;
    }
    return segment.type;
};

const resolveTimelineSegmentKey = (segment: MessageSegment, index: number, occurrences: Map<string, number>): string => {
    const baseKey = resolveTimelineSegmentBaseKey(segment, index);
    const nextCount = (occurrences.get(baseKey) ?? 0) + 1;
    occurrences.set(baseKey, nextCount);
    return `${baseKey}:${String(nextCount)}`;
};

export { resolveTimelineSegmentKey };
