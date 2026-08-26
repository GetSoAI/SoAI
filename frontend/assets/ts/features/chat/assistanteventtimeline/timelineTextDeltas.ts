/* SoAI - Assistant timeline text delta predicates [frontend/assets/ts/features/chat/assistanteventtimeline/timelineTextDeltas.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import type { AssistantEventTimelineItem } from '@features/chat/ChatTypes.ts';

const isAssistantTextDeltaEntry = (entry: AssistantEventTimelineItem): boolean => {
    return entry.eventType === 'assistant_text_delta';
};

const timelineHasAssistantTextDeltaEvent = (timeline: readonly AssistantEventTimelineItem[] | undefined, startIndex = 0): boolean => {
    if (!timeline) {
        return false;
    }
    const start = Math.max(0, startIndex);
    for (let index = start; index < timeline.length; index += 1) {
        const entry = timeline[index];
        if (entry !== undefined && isAssistantTextDeltaEntry(entry)) {
            return true;
        }
    }
    return false;
};

const timelineHasVisibleAssistantTextDelta = (timeline: readonly AssistantEventTimelineItem[] | undefined): boolean => {
    if (!timeline) {
        return false;
    }
    for (const entry of timeline) {
        if (!isAssistantTextDeltaEntry(entry)) {
            continue;
        }
        const delta = entry.payload.delta;
        if (isString(delta) && delta.trim().length > 0) {
            return true;
        }
    }
    return false;
};

export { timelineHasAssistantTextDeltaEvent, timelineHasVisibleAssistantTextDelta };
