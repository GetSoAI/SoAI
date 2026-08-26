/* SoAI - Assistant timeline inline status activity lifecycle updates [frontend/assets/ts/features/chat/assistanteventtimeline/timelineIndexStatusActivities.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AssistantActivityState, AssistantTimelinePayload } from '@core/realtime/eventcontracts/assistantTimelineTypes.ts';
import type { AssistantTimelineIndexState } from '@features/chat/assistanteventtimeline/timelineIndexState.ts';
import type { InlineStatusActivitySegment, InlineStatusActivitySegmentType } from '@features/chat/message/inlineStatusActivityIdentity.ts';

type AssistantStatusActivityEventType = 'loading_activity' | 'processing_activity' | 'wait_for_user_activity';

interface StatusActivityDescriptor {
    eventType: AssistantStatusActivityEventType;
    segmentType: InlineStatusActivitySegmentType;
}

const STATUS_ACTIVITY_DESCRIPTORS: Readonly<Record<AssistantStatusActivityEventType, StatusActivityDescriptor>> = Object.freeze({
    'loading_activity': {
        eventType: 'loading_activity',
        segmentType: 'inline_loading_activity'
    },
    'processing_activity': {
        eventType: 'processing_activity',
        segmentType: 'inline_processing_activity'
    },
    'wait_for_user_activity': {
        eventType: 'wait_for_user_activity',
        segmentType: 'inline_wait_for_user_activity'
    }
});

const buildStartedAtLookupKey = (segmentType: InlineStatusActivitySegmentType, startedAtMs: number): string => {
    return `${segmentType}:${String(startedAtMs)}`;
};

const buildLifecycleKey = (segmentType: InlineStatusActivitySegmentType, eventSequence: number): string => {
    return `${segmentType}:${String(eventSequence)}`;
};

const buildInlineStatusActivitySegment = (mapped: AssistantActivityState, descriptor: StatusActivityDescriptor, signatureSequence: number): InlineStatusActivitySegment => {
    const segment: InlineStatusActivitySegment = {
        type: descriptor.segmentType,
        status: mapped.status,
        startedAtMs: mapped.startedAtMs,
        signatureSequence: signatureSequence,
        durationMs: mapped.durationMs
    };
    if (mapped.reason !== undefined) {
        segment.reason = mapped.reason;
    }
    if (mapped.errorType !== undefined) {
        segment.errorType = mapped.errorType;
    }
    return segment;
};

const resolveStatusActivityLifecycleKey = (state: AssistantTimelineIndexState, descriptor: StatusActivityDescriptor, segment: InlineStatusActivitySegment, eventSequence: number): string => {
    const startedAtKey = buildStartedAtLookupKey(descriptor.segmentType, segment.startedAtMs);
    const openLifecycleKey = state.openStatusActivityLifecycleKeyByType.get(descriptor.segmentType) ?? null;
    if (openLifecycleKey !== null) {
        state.statusActivityLifecycleKeyByTypeAndStartedAt.set(startedAtKey, openLifecycleKey);
        return openLifecycleKey;
    }
    if (segment.status !== 'running') {
        const startedLifecycleKey = state.statusActivityLifecycleKeyByTypeAndStartedAt.get(startedAtKey) ?? null;
        if (startedLifecycleKey !== null) {
            return startedLifecycleKey;
        }
    }
    const lifecycleKey = buildLifecycleKey(descriptor.segmentType, eventSequence);
    state.statusActivityLifecycleKeyByTypeAndStartedAt.set(startedAtKey, lifecycleKey);
    return lifecycleKey;
};

const syncOpenLifecycleState = (state: AssistantTimelineIndexState, descriptor: StatusActivityDescriptor, segment: InlineStatusActivitySegment, lifecycleKey: string): void => {
    if (segment.status === 'running') {
        state.openStatusActivityLifecycleKeyByType.set(descriptor.segmentType, lifecycleKey);
        return;
    }
    const existingOpenKey = state.openStatusActivityLifecycleKeyByType.get(descriptor.segmentType) ?? null;
    if (existingOpenKey === lifecycleKey) {
        state.openStatusActivityLifecycleKeyByType.delete(descriptor.segmentType);
    }
};

const upsertStatusActivitySegment = (state: AssistantTimelineIndexState, lifecycleKey: string, eventSequence: number, contentIndexBefore: number, segment: InlineStatusActivitySegment): void => {
    const existing = state.timelineSegmentByLifecycleKey.get(lifecycleKey);
    const segmentWithLifecycle = { ...segment, activityLifecycleKey: lifecycleKey };
    if (existing) {
        existing.segment = segmentWithLifecycle;
        existing.revisionSequence = eventSequence;
        state.cachedTimelineSegments = null;
        return;
    }
    state.timelineSegmentByLifecycleKey.set(lifecycleKey, {
        contentIndexBefore,
        eventSequence,
        revisionSequence: eventSequence,
        segment: segmentWithLifecycle
    });
    state.cachedTimelineSegments = null;
};

const resolveActivity = (payload: AssistantTimelinePayload, eventType: AssistantStatusActivityEventType): AssistantActivityState | undefined => {
    if (eventType === 'loading_activity') return payload.loadingActivity;
    if (eventType === 'processing_activity') return payload.processingActivity;
    return payload.waitForUserActivity;
};

const applyStatusActivityTimelineEvent = (inputArguments: { state: AssistantTimelineIndexState; eventType: AssistantStatusActivityEventType; payload: AssistantTimelinePayload; eventSequence: number; contentIndexBefore: number }): void => {
    const descriptor = STATUS_ACTIVITY_DESCRIPTORS[inputArguments.eventType];
    const activity = resolveActivity(inputArguments.payload, inputArguments.eventType);
    if (activity === undefined) return;
    const segment = buildInlineStatusActivitySegment(activity, descriptor, inputArguments.eventSequence);
    const lifecycleKey = resolveStatusActivityLifecycleKey(inputArguments.state, descriptor, segment, inputArguments.eventSequence);
    upsertStatusActivitySegment(inputArguments.state, lifecycleKey, inputArguments.eventSequence, inputArguments.contentIndexBefore, segment);
    syncOpenLifecycleState(inputArguments.state, descriptor, segment, lifecycleKey);
};

export { applyStatusActivityTimelineEvent };
export type { AssistantStatusActivityEventType };
