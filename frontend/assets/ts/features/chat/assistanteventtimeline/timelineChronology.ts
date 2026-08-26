/* SoAI - Assistant event timeline chronology contracts [frontend/assets/ts/features/chat/assistanteventtimeline/timelineChronology.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { formatHashSignature } from '@core/realtime/streammanager/hashSignature.ts';
import type { AssistantEventTimelineItem } from '@features/chat/ChatTypes.ts';
import type { MessageSegment } from '@features/chat/message/messageSegments.ts';

interface AssistantChronologyRenderEntry {
    contentIndexBefore: number;
    eventSequence: number;
    revisionSequence: number;
    sameAnchorOrder?: number;
    segment: MessageSegment;
}

const compareAssistantChronologyRenderEntry = (left: AssistantChronologyRenderEntry, right: AssistantChronologyRenderEntry): number => {
    if (left.contentIndexBefore !== right.contentIndexBefore) {
        return left.contentIndexBefore - right.contentIndexBefore;
    }
    if (left.eventSequence !== right.eventSequence) {
        return left.eventSequence - right.eventSequence;
    }
    return (left.sameAnchorOrder ?? 0) - (right.sameAnchorOrder ?? 0);
};

const resolveChronologicalRenderAnchor = (payloadContentIndexBefore: number, eventVisibleTextLength: number): number => {
    if (!Number.isFinite(payloadContentIndexBefore) || !Number.isInteger(payloadContentIndexBefore) || payloadContentIndexBefore < 0) {
        throw new Error('Assistant event timeline activity anchor must be a non-negative integer.');
    }
    if (!Number.isFinite(eventVisibleTextLength) || !Number.isInteger(eventVisibleTextLength) || eventVisibleTextLength < 0) {
        throw new Error('Assistant event timeline visible text length must be a non-negative integer.');
    }
    return eventVisibleTextLength;
};

const resolveAssistantTimelineEventSignature = (event: AssistantEventTimelineItem): string => {
    return [String(event.sourceSequenceStart ?? event.sequence), String(event.sequence), String(event.assistantRevision), event.eventType, formatHashSignature(event.payload)].join(':');
};

const resolveAssistantTimelineSemanticEventSignature = (event: AssistantEventTimelineItem): string => {
    return [String(event.sequence), String(event.assistantRevision), event.eventType, formatHashSignature(event.payload)].join(':');
};

export { compareAssistantChronologyRenderEntry, resolveAssistantTimelineEventSignature, resolveAssistantTimelineSemanticEventSignature, resolveChronologicalRenderAnchor };
export type { AssistantChronologyRenderEntry };
