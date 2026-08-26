/* SoAI - Assistant stream message progress parsing [frontend/assets/ts/features/chat/chatstreamservice/assistantStreamMessageState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isNumber, isPlainObject } from '@core/typeGuards.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';

const resolveAssistantTimelineProgress = (message: ChatMessage | null): { entryCount: number; assistantRevision: number } => {
    if (!message) {
        return { entryCount: 0, assistantRevision: 0 };
    }
    const timeline = message.assistantEventTimeline;
    if (!isArray(timeline)) {
        return { entryCount: 0, assistantRevision: 0 };
    }
    const length = timeline.length;
    if (length <= 0) {
        return { entryCount: 0, assistantRevision: 0 };
    }
    const last = timeline[length - 1];
    if (!last || typeof last !== 'object') {
        return { entryCount: length, assistantRevision: 0 };
    }
    const lastRecord = isPlainObject(last) ? last : null;
    const revisionValue = lastRecord ? lastRecord.assistantRevision : null;
    const assistantRevision = isNumber(revisionValue) && Number.isFinite(revisionValue) && Number.isInteger(revisionValue) && revisionValue > 0 ? revisionValue : 0;
    return { entryCount: length, assistantRevision };
};

export { resolveAssistantTimelineProgress };
