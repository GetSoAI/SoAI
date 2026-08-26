/* SoAI - Chat feature stream run session event application [frontend/assets/ts/features/chat/chatstreamservice/streamRunSessionEventApplication.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import type { StreamRuntime } from '@features/chat/chatstreamservice/contracts.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';
import type { ChatStreamTimelineEvent } from '@core/realtime/eventcontracts/chatStreamEnvelope.ts';
import { advanceAssistantRevisionAndNotifyTimelineEvent, commitAssistantTimelineEvent, prepareAssistantTimelineEvent, type PreparedAssistantTimelineEvent } from '@features/chat/chatstreamservice/streamAssistantTimelineEventState.ts';
import { resolveAssistantMessageIdentity, resolvePositiveAssistantRevision } from '@core/chat/assistantIdentity.ts';
import { applyCancelledStreamEvent, applyCompletedStreamEvent, applyErrorStreamEvent } from '@features/chat/chatstreamservice/streamTerminalEventApplication.ts';
import { clearChatStreamStatusPreview } from '@features/chat/chatstreamservice/streamStatusPreviewMessageState.ts';

const TIMELINE_ONLY_EVENT_TYPES = new Set<string>(['thinking_phase', 'tool_call_created', 'tool_call_started', 'tool_call_completed']);

const applyStreamEventToSession = async (inputArguments: { event: ChatStreamTimelineEvent; session: ChatStreamSession; runtime: StreamRuntime; failProtocol: (message: string, errorCode?: string | null) => void; markDone: () => void; notifyUser: boolean }): Promise<void> => {
    const { event, session, runtime, failProtocol, markDone, notifyUser } = inputArguments;
    const payload = event.payload;
    const identity = resolveAssistantMessageIdentity({
        assistantTimestamp: payload.assistantAtMs,
        assistantTurnTimestamp: payload.assistantTurnAtMs,
        modelVariantIndex: payload.modelVariantIndex
    });
    if (identity === null || identity.assistantTimestamp !== session.assistantTimestamp) {
        return;
    }
    if (identity.assistantTurnTimestamp !== session.assistantTurnTimestamp) {
        failProtocol('Chat stream protocol error: payload assistant_turn_at_ms does not match the active session.');
        return;
    }
    if (identity.modelVariantIndex !== session.modelVariantIndex) {
        failProtocol('Chat stream protocol error: payload model_variant_index does not match the active session.');
        return;
    }
    const assistantRevision = resolvePositiveAssistantRevision(payload.assistantRevision);
    if (assistantRevision === null) {
        failProtocol('Chat stream protocol error: payload assistant_revision must be a positive integer.');
        return;
    }
    let prepared: PreparedAssistantTimelineEvent;
    try {
        prepared = prepareAssistantTimelineEvent(session, event, payload, assistantRevision);
    } catch (error) {
        const runtimeError = ensureError(error);
        if (event.eventType === 'thinking_phase') {
            failProtocol(`Chat stream protocol error: invalid thinking_phase payload. ${runtimeError.message}`);
        } else if (event.eventType === 'tool_call_created' || event.eventType === 'tool_call_started' || event.eventType === 'tool_call_completed') {
            failProtocol(`Chat stream protocol error: invalid ${event.eventType} payload. ${runtimeError.message}`);
        } else {
            failProtocol(runtimeError.message);
        }
        throw runtimeError;
    }

    commitAssistantTimelineEvent(session, prepared, assistantRevision);

    if (payload.usagePreview !== undefined) session.usagePreview = payload.usagePreview;

    if (event.eventType === 'loading_activity') {
        if (payload.loadingActivity === undefined) {
            failProtocol('Chat stream protocol error: invalid loading_activity payload.');
            return;
        }
        if (event.sequence === 0) {
            await runtime.notifyCheckpoint(session, { type: 'initial-timeline' });
        } else {
            advanceAssistantRevisionAndNotifyTimelineEvent(session, runtime);
        }
        return;
    }

    if (event.eventType === 'processing_activity') {
        if (payload.processingActivity === undefined) {
            failProtocol('Chat stream protocol error: invalid processing_activity payload.');
            return;
        }
        advanceAssistantRevisionAndNotifyTimelineEvent(session, runtime);
        return;
    }

    if (event.eventType === 'wait_for_user_activity') {
        if (payload.waitForUserActivity === undefined) {
            failProtocol('Chat stream protocol error: invalid wait_for_user_activity payload.');
            return;
        }
        advanceAssistantRevisionAndNotifyTimelineEvent(session, runtime);
        return;
    }

    if (event.eventType === 'assistant_text_delta') {
        const delta = payload.delta;
        if (delta === undefined) {
            failProtocol('Chat stream protocol error: assistant_text_delta.delta must be a non-empty string.');
            return;
        }
        clearChatStreamStatusPreview(session.assistantMessage);
        runtime.notify(session, { type: 'text-delta', textDelta: delta });
        return;
    }

    if (event.eventType === 'assistant_image') {
        if (payload.image === undefined) {
            failProtocol('Chat stream protocol error: assistant_image.image.url must be a non-empty string.');
            return;
        }
        runtime.notify(session, { type: 'image' });
        return;
    }

    if (TIMELINE_ONLY_EVENT_TYPES.has(event.eventType)) {
        if (event.eventType === 'tool_call_created') {
            clearChatStreamStatusPreview(session.assistantMessage);
        }
        advanceAssistantRevisionAndNotifyTimelineEvent(session, runtime);
        return;
    }

    if (event.eventType === 'completed') {
        applyCompletedStreamEvent({ session, runtime, payload, assistantRevision, failProtocol, markDone, notifyUser });
        return;
    }

    if (event.eventType === 'cancelled') {
        applyCancelledStreamEvent({ session, runtime, payload, assistantRevision, failProtocol, markDone, notifyUser });
        return;
    }

    if (event.eventType === 'error') {
        applyErrorStreamEvent({ session, runtime, payload, assistantRevision, failProtocol, markDone, notifyUser });
        return;
    }

    failProtocol(`Chat stream protocol error: unsupported event type "${event.eventType}".`);
};

export { applyStreamEventToSession };
