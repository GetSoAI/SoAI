/* SoAI - Atomic assistant timeline event state [frontend/assets/ts/features/chat/chatstreamservice/streamAssistantTimelineEventState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AssistantEventTimelineItem, AssistantTimelinePayload } from '@core/realtime/eventcontracts/assistantTimelineTypes.ts';
import { isArray } from '@core/typeGuards.ts';
import { resolveLatestLoadingActivityFromTimeline } from '@features/chat/assistanteventtimeline/activityState.ts';
import { resetAssistantTimelineIndexState } from '@features/chat/assistanteventtimeline/timelineIndexState.ts';
import { updateAssistantTimelineIndexState } from '@features/chat/assistanteventtimeline/timelineIndexUpdate.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { StreamRuntime } from '@features/chat/chatstreamservice/contracts.ts';
import { appendAssistantTextDelta } from '@features/chat/chatstreamservice/streamMessageUpdates.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';
import type { ChatStreamTimelineEvent } from '@core/realtime/eventcontracts/chatStreamEnvelope.ts';

type PreparedAssistantTimelineEvent = {
    message: ChatMessage;
};

const buildIncomingItem = (event: ChatStreamTimelineEvent, payload: AssistantTimelinePayload, assistantRevision: number, projected: boolean): AssistantEventTimelineItem => ({
    ...(projected ? { sourceSequenceStart: event.sequence } : {}),
    sequence: event.sequence,
    assistantRevision,
    eventType: event.eventType,
    payload
});

const validateTimelinePayload = (eventType: string, payload: AssistantTimelinePayload): void => {
    if (eventType === 'loading_activity' && payload.loadingActivity === undefined) throw new Error('Chat stream protocol error: invalid loading_activity payload.');
    if (eventType === 'processing_activity' && payload.processingActivity === undefined) throw new Error('Chat stream protocol error: invalid processing_activity payload.');
    if (eventType === 'wait_for_user_activity' && payload.waitForUserActivity === undefined) throw new Error('Chat stream protocol error: invalid wait_for_user_activity payload.');
    if (eventType === 'assistant_text_delta' && payload.delta === undefined) throw new Error('Chat stream protocol error: assistant_text_delta.delta must be a non-empty string.');
    if (eventType === 'assistant_image' && payload.image === undefined) throw new Error('Chat stream protocol error: assistant_image.image.url must be a non-empty string.');
    if (eventType === 'cancelled' && (!payload.reason || !payload.code)) throw new Error('Chat stream protocol error: cancelled requires reason and code.');
    if (eventType === 'error' && (!payload.message || !payload.code || !payload.referenceId)) throw new Error('Chat stream protocol error: error requires message, code, and reference_id.');
    const supported = eventType === 'loading_activity' || eventType === 'processing_activity' || eventType === 'wait_for_user_activity' || eventType === 'assistant_text_delta' || eventType === 'assistant_image' || eventType === 'thinking_phase' || eventType === 'tool_call_created' || eventType === 'tool_call_started' || eventType === 'tool_call_completed' || eventType === 'completed' || eventType === 'cancelled' || eventType === 'error';
    if (!supported) throw new Error(`Chat stream protocol error: unsupported event type "${eventType}".`);
};

const prepareAssistantTimelineEvent = (session: ChatStreamSession, event: ChatStreamTimelineEvent, payload: AssistantTimelinePayload, assistantRevision: number): PreparedAssistantTimelineEvent => {
    const current = isArray(session.assistantMessage.assistantEventTimeline) ? session.assistantMessage.assistantEventTimeline : [];
    if (event.sequence !== session.assistantRevision || assistantRevision !== event.sequence + 1) {
        throw new Error(`Chat stream protocol error: expected sequence ${String(session.assistantRevision)} but received ${String(event.sequence)}.`);
    }
    validateTimelinePayload(event.eventType, payload);
    const projected = session.assistantMessage.assistantTimelineType === 'projection';
    if (!projected && event.sequence !== current.length) {
        throw new Error('Canonical assistant event timeline sequence must equal its array index.');
    }
    const timeline = [...current, buildIncomingItem(event, payload, assistantRevision, projected)];
    if ((event.eventType === 'completed' || event.eventType === 'cancelled' || event.eventType === 'error') && resolveLatestLoadingActivityFromTimeline(timeline) === null) {
        throw new Error(`Chat stream protocol error: ${event.eventType} requires prior loading_activity.`);
    }
    const candidate: ChatMessage = { ...session.assistantMessage, assistantEventTimeline: timeline, assistantTimelineType: projected ? 'projection' : 'canonical' };
    if (event.eventType === 'assistant_text_delta' && payload.delta !== undefined) appendAssistantTextDelta(candidate, payload.delta);
    return { message: candidate };
};

const commitAssistantTimelineEvent = (session: ChatStreamSession, prepared: PreparedAssistantTimelineEvent, assistantRevision: number): void => {
    const baseTimeline = isArray(session.assistantMessage.assistantEventTimeline) ? session.assistantMessage.assistantEventTimeline : [];
    try {
        updateAssistantTimelineIndexState(session.assistantTimelineIndexState, prepared.message, {
            acceptedAppend: {
                baseTimeline,
                baseRevision: session.assistantRevision,
                candidateRevision: assistantRevision
            }
        });
    } catch (error) {
        resetAssistantTimelineIndexState(session.assistantTimelineIndexState);
        updateAssistantTimelineIndexState(session.assistantTimelineIndexState, session.assistantMessage);
        throw error;
    }
    session.assistantMessage = prepared.message;
    session.assistantRevision = assistantRevision;
};

const advanceAssistantRevisionAndNotifyTimelineEvent = (session: ChatStreamSession, runtime: StreamRuntime): void => {
    runtime.notify(session, { type: 'timeline-event' });
};

export { advanceAssistantRevisionAndNotifyTimelineEvent, commitAssistantTimelineEvent, prepareAssistantTimelineEvent };
export type { PreparedAssistantTimelineEvent };
