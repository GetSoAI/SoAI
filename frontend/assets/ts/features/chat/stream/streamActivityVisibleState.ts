/* SoAI - Streaming activity visible state tracking [frontend/assets/ts/features/chat/stream/streamActivityVisibleState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isObject, isPositiveInteger, isString } from '@core/typeGuards.ts';
import type { ChatContentSegment, ChatMessage } from '@features/chat/ChatTypes.ts';
import { resolveToolProjectionVisibleStreamingSignature } from '@features/chat/toolactivity/toolProjectionStreamingSignature.ts';

type StreamActivityVisibleState = {
    textLength: number;
    timelineLength: number;
    projectionFingerprint: string;
};

const resolveTextSegmentLength = (value: ChatContentSegment): number => {
    if (isString(value)) {
        return value.length;
    }
    if (!isObject(value)) {
        return 0;
    }
    const textValue = 'text' in value ? value.text : undefined;
    if (isString(textValue)) {
        return textValue.length;
    }
    const mappedValue = 'value' in value ? value.value : undefined;
    if (isString(mappedValue)) {
        return mappedValue.length;
    }
    return 0;
};

const resolveStreamMessageTextLength = (message: ChatMessage): number => {
    const content = message.content;
    if (isString(content)) {
        return content.length;
    }
    if (!isArray(content)) {
        return 0;
    }
    let totalLength = 0;
    for (const segment of content) {
        totalLength += resolveTextSegmentLength(segment);
    }
    return totalLength;
};

const resolveStreamTimelineLength = (message: ChatMessage): number => {
    const timeline = message.assistantEventTimeline;
    if (!isArray(timeline)) {
        return 0;
    }
    return timeline.length;
};

const resolveStreamStatusPreviewText = (message: ChatMessage): string => {
    const candidate = message.streamStatusPreviewText;
    if (!isString(candidate)) {
        return '';
    }
    return candidate.trim();
};

const resolveStreamStatusPreviewCooldownMs = (message: ChatMessage): number => {
    if (!resolveStreamStatusPreviewText(message)) {
        return 0;
    }
    const candidate = message.streamStatusPreviewCooldownMs;
    if (!isPositiveInteger(candidate)) {
        throw new Error('Stream render snapshot requires a positive status preview cooldown.');
    }
    return candidate;
};

const resolveStreamActivityProjectionFingerprint = (message: ChatMessage): string => {
    const projections = message.toolCallProjections;
    if (!isArray(projections) || projections.length === 0) {
        return '';
    }
    return projections.map((projection) => resolveToolProjectionVisibleStreamingSignature(projection)).join('|');
};

const resolveStreamActivityVisibleState = (message: ChatMessage): StreamActivityVisibleState => ({
    textLength: resolveStreamMessageTextLength(message),
    timelineLength: resolveStreamTimelineLength(message),
    projectionFingerprint: resolveStreamActivityProjectionFingerprint(message)
});

const streamActivityVisibleStatesMatch = (left: StreamActivityVisibleState | null, right: StreamActivityVisibleState): boolean => {
    return left !== null && left.textLength === right.textLength && left.timelineLength === right.timelineLength && left.projectionFingerprint === right.projectionFingerprint;
};

export { resolveStreamActivityVisibleState, resolveStreamMessageTextLength, resolveStreamStatusPreviewCooldownMs, resolveStreamStatusPreviewText, resolveStreamTimelineLength, streamActivityVisibleStatesMatch };
export type { StreamActivityVisibleState };
