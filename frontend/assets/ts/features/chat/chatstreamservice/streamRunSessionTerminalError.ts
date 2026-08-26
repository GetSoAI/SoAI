/* SoAI - Chat feature stream run session terminal error [frontend/assets/ts/features/chat/chatstreamservice/streamRunSessionTerminalError.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readRequiredTrimmedStringMessageValue } from '@core/types/payloadValueReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isPositiveInteger } from '@core/typeGuards.ts';
import type { AssistantEventTimelineItem } from '@features/chat/ChatTypes.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';
import { createAssistantTimelineIndexState } from '@features/chat/assistanteventtimeline/timelineIndexState.ts';
import { updateAssistantTimelineIndexState } from '@features/chat/assistanteventtimeline/timelineIndexUpdate.ts';
import type { AssistantActivityState } from '@core/realtime/eventcontracts/assistantTimelineTypes.ts';

const normalizeTerminalString = (value: JsonValue | null | undefined, context: string): string => {
    return readRequiredTrimmedStringMessageValue(value, `${context} requires a non-empty string.`);
};

const requireTimeline = (value: AssistantEventTimelineItem[] | undefined): AssistantEventTimelineItem[] | null => {
    if (!value) {
        throw new Error('Chat stream terminal error requires an assistant event timeline array.');
    }
    if (value.length === 0) {
        return null;
    }
    return value;
};

const resolveLatestLoadingActivity = (timeline: AssistantEventTimelineItem[]): AssistantActivityState | null => {
    let latest: AssistantActivityState | null = null;
    for (const event of timeline) {
        if (event.eventType !== 'loading_activity') {
            continue;
        }
        const loadingPayload = event.payload.loadingActivity;
        if (loadingPayload === undefined) throw new Error('Chat stream terminal error requires a loading_activity payload object.');
        latest = loadingPayload;
    }
    return latest;
};

const hasTerminalErrorEvent = (timeline: AssistantEventTimelineItem[], code: string, referenceId: string): boolean => {
    for (const event of timeline) {
        if (event.eventType !== 'error') {
            continue;
        }
        const codeValue = event.payload.code;
        const messageValue = event.payload.message;
        const referenceIdValue = event.payload.referenceId;
        normalizeTerminalString(codeValue, 'Chat stream terminal error event code');
        normalizeTerminalString(messageValue, 'Chat stream terminal error event message');
        normalizeTerminalString(referenceIdValue, 'Chat stream terminal error event reference ID');
        if (codeValue === code && referenceIdValue === referenceId) return true;
        throw new Error('Chat stream terminal error conflicts with the existing terminal event identity.');
    }
    return false;
};

const hasCompleteTerminalLoadingError = (payload: AssistantActivityState): boolean => {
    return payload.status === 'error' && payload.reason !== undefined && payload.errorType !== undefined;
};

const resolveLatestTerminalTimelineError = (timeline: AssistantEventTimelineItem[] | undefined): { message: string; code: string; referenceId: string; previewContract?: JsonValue } | null => {
    if (!timeline) return null;
    for (let index = timeline.length - 1; index >= 0; index -= 1) {
        const event = timeline[index];
        if (!event || event.eventType !== 'error') continue;
        const message = normalizeTerminalString(event.payload.message, 'Chat stream terminal error event message');
        const code = normalizeTerminalString(event.payload.code, 'Chat stream terminal error event code');
        const referenceId = normalizeTerminalString(event.payload.referenceId, 'Chat stream terminal error event reference ID');
        return { message, code, referenceId, ...(event.payload.previewContract !== undefined ? { previewContract: event.payload.previewContract } : {}) };
    }
    return null;
};

const writeTerminalErrorToTimeline = (session: ChatStreamSession, message: string, errorCode: string | null, referenceId: string = session.requestId): void => {
    const normalizedCode = normalizeTerminalString(errorCode, 'Chat stream terminal error code');
    const normalizedMessage = normalizeTerminalString(message, 'Chat stream terminal error message');
    const normalizedReferenceId = normalizeTerminalString(referenceId, 'Chat stream terminal error reference ID');
    const assistantTimestamp = session.assistantTimestamp;
    const assistantTurnTimestamp = session.assistantTurnTimestamp;
    const modelVariantIndex = session.modelVariantIndex;
    if (!isPositiveInteger(assistantTimestamp)) {
        throw new Error('Chat stream terminal error requires a valid assistant timestamp');
    }
    const currentTimeline = requireTimeline(session.assistantMessage.assistantEventTimeline);
    const timeline = currentTimeline === null ? null : [...currentTimeline];
    if (timeline === null) {
        return;
    }

    const latestLoadingActivity = resolveLatestLoadingActivity(timeline);
    if (latestLoadingActivity === null) {
        throw new Error('Chat stream terminal error requires an existing loading_activity timeline event.');
    }
    const hasTerminalLoadingError = hasCompleteTerminalLoadingError(latestLoadingActivity);
    const terminalErrorEventExists = hasTerminalErrorEvent(timeline, normalizedCode, normalizedReferenceId);

    let nextSequence = 0;
    let nextRevision = 1;
    if (timeline.length > 0) {
        const last = timeline[timeline.length - 1];
        if (last) {
            nextSequence = last.sequence + 1;
            nextRevision = last.assistantRevision + 1;
        }
    }

    if (!hasTerminalLoadingError) {
        timeline.push({
            ...(session.assistantMessage.assistantTimelineType === 'projection' ? { sourceSequenceStart: nextSequence } : {}),
            sequence: nextSequence,
            assistantRevision: nextRevision,
            eventType: 'loading_activity',
            payload: {
                assistantAtMs: assistantTimestamp,
                assistantTurnAtMs: assistantTurnTimestamp,
                assistantRevision: nextRevision,
                modelVariantIndex,
                loadingActivity: {
                    status: 'error',
                    startedAtMs: latestLoadingActivity.startedAtMs,
                    durationMs: latestLoadingActivity.durationMs,
                    reason: normalizedMessage,
                    errorType: normalizedCode
                }
            }
        });
        nextSequence += 1;
        nextRevision += 1;
    }

    if (!terminalErrorEventExists) {
        timeline.push({
            ...(session.assistantMessage.assistantTimelineType === 'projection' ? { sourceSequenceStart: nextSequence } : {}),
            sequence: nextSequence,
            assistantRevision: nextRevision,
            eventType: 'error',
            payload: {
                assistantAtMs: assistantTimestamp,
                assistantTurnAtMs: assistantTurnTimestamp,
                assistantRevision: nextRevision,
                modelVariantIndex,
                message: normalizedMessage,
                code: normalizedCode,
                referenceId: normalizedReferenceId
            }
        });
        nextRevision += 1;
    }

    const candidateMessage = {
        ...session.assistantMessage,
        assistantTurnAtMs: assistantTurnTimestamp,
        modelVariantIndex,
        assistantEventTimeline: timeline
    };
    const candidateIndexState = createAssistantTimelineIndexState();
    updateAssistantTimelineIndexState(candidateIndexState, candidateMessage);
    session.assistantMessage.assistantTurnAtMs = assistantTurnTimestamp;
    session.assistantMessage.modelVariantIndex = modelVariantIndex;
    session.assistantMessage.assistantEventTimeline = timeline;
    session.assistantRevision = Math.max(session.assistantRevision, nextRevision - 1);
    session.assistantTimelineIndexState = candidateIndexState;
};

export { resolveLatestTerminalTimelineError, writeTerminalErrorToTimeline };
