/* SoAI - Chat feature timeline index update [frontend/assets/ts/features/chat/assistanteventtimeline/timelineIndexUpdate.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray } from '@core/typeGuards.ts';
import { formatHashSignature } from '@core/realtime/streammanager/hashSignature.ts';
import { resolveAssistantTimelineEventSignature } from '@features/chat/assistanteventtimeline/timelineChronology.ts';
import { applyThinkingPhaseUpdate } from '@features/chat/assistanteventtimeline/timelineIndexThinkingUpdates.ts';
import { applyStatusActivityTimelineEvent } from '@features/chat/assistanteventtimeline/timelineIndexStatusActivities.ts';
import { applyToolCallLifecycleUpdate, applyToolCallProjectionUpdate } from '@features/chat/assistanteventtimeline/timelineIndexToolUpdates.ts';
import { resetAssistantTimelineIndexState, type AssistantTimelineIndexState } from '@features/chat/assistanteventtimeline/timelineIndexState.ts';
import type { AssistantEventTimelineItem, ChatMessage } from '@features/chat/ChatTypes.ts';
import { isAssistantMessageRole } from '@features/chat/message/messageRole.ts';
import type { MessageSegment } from '@features/chat/message/messageSegments.ts';

const resolveTimeline = (message: ChatMessage): AssistantEventTimelineItem[] => {
    const rawTimeline = message.assistantEventTimeline;
    if (!isArray(rawTimeline) || rawTimeline.length === 0) {
        return [];
    }
    return rawTimeline;
};

const applyToolCallProjections = (state: AssistantTimelineIndexState, message: ChatMessage): void => {
    const projections = message.toolCallProjections;
    const observedProjectionOnlyCallIds = new Set<string>();
    if (!isArray(projections) || projections.length === 0) {
        removeMissingProjectionOnlyToolCalls(state, observedProjectionOnlyCallIds);
        return;
    }
    for (const projection of projections) {
        const applied = applyToolCallProjectionUpdate(state, projection, resolveAssistantVisibleContentLength(state));
        if (applied.projectionOnly) {
            observedProjectionOnlyCallIds.add(applied.callId);
        }
    }
    removeMissingProjectionOnlyToolCalls(state, observedProjectionOnlyCallIds);
};

const removeMissingProjectionOnlyToolCalls = (state: AssistantTimelineIndexState, observedCallIds: Set<string>): void => {
    let changed = false;
    for (const callId of state.projectionOnlyToolCallIds) {
        if (observedCallIds.has(callId)) {
            continue;
        }
        const existing = state.toolActivityByCallId.get(callId);
        if (existing !== undefined) {
            state.toolCallIdBySequenceIndex.delete(existing.sequenceIndex);
        }
        state.toolActivityByCallId.delete(callId);
        state.toolRenderSequenceByCallId.delete(callId);
        state.toolRenderAnchorByCallId.delete(callId);
        state.toolLifecycleStatusRankByCallId.delete(callId);
        changed = true;
    }
    if (!changed) {
        return;
    }
    state.projectionOnlyToolCallIds.clear();
    for (const callId of observedCallIds) {
        state.projectionOnlyToolCallIds.add(callId);
    }
    state.cachedToolActivity = null;
};

const resolveAssistantVisibleContentLength = (state: AssistantTimelineIndexState): number => {
    return state.assistantVisibleTextCodePointLength;
};

const appendAssistantTextDelta = (state: AssistantTimelineIndexState, deltaValue: string): void => {
    state.hasAssistantTextDeltas = true;
    state.assistantVisibleText += deltaValue;
    state.assistantVisibleTextCodePointLength += Array.from(deltaValue).length;
    state.assistantTextIsStreamingActive = true;
};

const upsertActivitySegment = (state: AssistantTimelineIndexState, lifecycleKey: string, eventSequence: number, revisionSequence: number, contentIndexBefore: number, segment: MessageSegment): void => {
    const existing = state.timelineSegmentByLifecycleKey.get(lifecycleKey);
    if (existing) {
        existing.segment = segment;
        existing.revisionSequence = revisionSequence;
        existing.contentIndexBefore = contentIndexBefore;
    } else {
        state.timelineSegmentByLifecycleKey.set(lifecycleKey, { contentIndexBefore, eventSequence, revisionSequence, segment });
    }
    state.cachedTimelineSegments = null;
};

const resetTimelineIndexIfProcessedPrefixChanged = (state: AssistantTimelineIndexState, timeline: AssistantEventTimelineItem[]): void => {
    if (timeline.length < state.processedLength) {
        resetAssistantTimelineIndexState(state);
        return;
    }
    if (state.timelineReference === timeline) {
        return;
    }
    for (let index = 0; index < state.processedLength; index += 1) {
        const event = timeline[index];
        if (!event) {
            resetAssistantTimelineIndexState(state);
            return;
        }
        if (state.processedEventSignatures[index] !== resolveAssistantTimelineEventSignature(event)) {
            resetAssistantTimelineIndexState(state);
            return;
        }
    }
};

const appendTimelineProjectionHash = (currentHash: string, eventSignature: string): string => {
    return formatHashSignature(`${currentHash}|${eventSignature}`);
};

const readAssistantRevision = (event: AssistantEventTimelineItem): number => {
    const revision = event.assistantRevision;
    if (typeof revision !== 'number' || !Number.isFinite(revision) || !Number.isInteger(revision) || revision <= 0) {
        return 0;
    }
    return revision;
};

const updateAssistantTimelineIndexState = (state: AssistantTimelineIndexState, message: ChatMessage): void => {
    if (!isAssistantMessageRole(message)) {
        return;
    }

    const timeline = resolveTimeline(message);
    if (timeline.length === 0) {
        if (state.processedLength > 0 || state.processedEventSignatures.length > 0) {
            resetAssistantTimelineIndexState(state);
        }
        state.timelineReference = null;
        applyToolCallProjections(state, message);
        return;
    }
    resetTimelineIndexIfProcessedPrefixChanged(state, timeline);
    state.timelineReference = timeline;

    for (let index = state.processedLength; index < timeline.length; index += 1) {
        const event = timeline[index];
        if (!event) {
            throw new Error('Assistant event timeline sequence must be contiguous starting at 0.');
        }
        const previousEvent = message.assistantTimelineType === 'projection' && index > 0 ? timeline[index - 1] : null;
        const sourceSequenceStart = message.assistantTimelineType === 'projection' ? (event.sourceSequenceStart ?? event.sequence) : event.sequence;
        const expectedSourceSequenceStart = previousEvent ? previousEvent.sequence + 1 : 0;
        if (message.assistantTimelineType === 'projection') {
            if (sourceSequenceStart !== expectedSourceSequenceStart || event.sequence < sourceSequenceStart || (sourceSequenceStart !== event.sequence && event.eventType !== 'assistant_text_delta')) {
                throw new Error('Assistant event timeline projection source ranges must be contiguous.');
            }
        } else if (event.sequence !== index || sourceSequenceStart !== event.sequence) {
            throw new Error('Assistant event timeline sequence must be contiguous starting at 0.');
        }
        if (event.assistantRevision !== event.sequence + 1) throw new Error('Assistant event timeline revision must equal sequence + 1.');
        const eventSignature = resolveAssistantTimelineEventSignature(event);
        state.processedEventSignatures[index] = eventSignature;
        state.timelineProjectionHash = appendTimelineProjectionHash(state.timelineProjectionHash, eventSignature);
        const assistantRevision = readAssistantRevision(event);
        if (assistantRevision > 0) {
            state.timelineLatestAssistantRevision = assistantRevision;
        }
        const payload = event.payload;

        if (event.eventType === 'assistant_text_delta') {
            const deltaValue = payload.delta;
            if (deltaValue !== undefined) {
                appendAssistantTextDelta(state, deltaValue);
                state.cachedTimelineSegments = null;
            }
            state.processedLength = index + 1;
            continue;
        }

        if (event.eventType === 'assistant_image') {
            const imageValue = payload.image;
            if (imageValue === undefined) {
                throw new Error('Assistant event timeline assistant_image payload is invalid.');
            }
            const segment: MessageSegment = {
                type: 'image',
                imageUrl: imageValue.url,
                title: ''
            };
            state.hasAssistantImages = true;
            upsertActivitySegment(state, `assistant_image:${String(event.sequence)}`, event.sequence, event.sequence, resolveAssistantVisibleContentLength(state), segment);
            state.processedLength = index + 1;
            continue;
        }

        if (event.eventType === 'tool_call_created' || event.eventType === 'tool_call_started' || event.eventType === 'tool_call_completed') {
            applyToolCallLifecycleUpdate(state, event.sequence, payload, event.eventType, resolveAssistantVisibleContentLength(state));
            state.processedLength = index + 1;
            continue;
        }

        if (event.eventType === 'thinking_phase') {
            applyThinkingPhaseUpdate(state, event.sequence, payload, resolveAssistantVisibleContentLength(state));
            state.processedLength = index + 1;
            continue;
        }

        if (event.eventType === 'loading_activity') {
            applyStatusActivityTimelineEvent({ state, eventType: 'loading_activity', payload, eventSequence: event.sequence, contentIndexBefore: resolveAssistantVisibleContentLength(state) });
            state.processedLength = index + 1;
            continue;
        }

        if (event.eventType === 'processing_activity') {
            applyStatusActivityTimelineEvent({ state, eventType: 'processing_activity', payload, eventSequence: event.sequence, contentIndexBefore: resolveAssistantVisibleContentLength(state) });
            state.processedLength = index + 1;
            continue;
        }

        if (event.eventType === 'wait_for_user_activity') {
            applyStatusActivityTimelineEvent({ state, eventType: 'wait_for_user_activity', payload, eventSequence: event.sequence, contentIndexBefore: resolveAssistantVisibleContentLength(state) });
            state.processedLength = index + 1;
            continue;
        }

        if (event.eventType === 'completed' || event.eventType === 'cancelled' || event.eventType === 'error') {
            state.hasTerminalEvent = true;
            state.assistantTextIsStreamingActive = false;
            state.cachedTimelineSegments = null;
            state.processedLength = index + 1;
            continue;
        }

        state.processedLength = index + 1;
    }
    applyToolCallProjections(state, message);
};

export { updateAssistantTimelineIndexState };
