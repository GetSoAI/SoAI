/* SoAI - Chat feature timeline index resolution [frontend/assets/ts/features/chat/assistanteventtimeline/timelineIndexResolution.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { cloneCollapsedOverrideRecord } from '@features/chat/assistanteventtimeline/collapsedOverrideRecords.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { ActivitySegmentEntry, AssistantTimelineIndexState, AssistantTimelineOverlays } from '@features/chat/assistanteventtimeline/timelineIndexState.ts';
import type { MessageSegment } from '@features/chat/message/messageSegments.ts';

const TOOL_SEQUENCE_INDEX_ERROR = 'Assistant event timeline tool sequence_index values must be contiguous starting at 0.';
const THINKING_SEQUENCE_INDEX_ERROR = 'Assistant event timeline thinking_phase sequence_index values must be contiguous starting at 0.';

const resolveCollapsedOverrideMap = (value: JsonValue | null | undefined): Map<string, boolean> => {
    const overrides = new Map<string, boolean>();
    const record = cloneCollapsedOverrideRecord(value);
    if (record === null) {
        return overrides;
    }
    for (const [callId, collapsed] of Object.entries(record)) {
        overrides.set(callId, collapsed);
    }
    return overrides;
};

const resolveAssistantTimelineActivitySegments = (state: AssistantTimelineIndexState): ActivitySegmentEntry[] => {
    if (state.cachedTimelineSegments) {
        return state.cachedTimelineSegments;
    }
    const entries = Array.from(state.timelineSegmentByLifecycleKey.values()).sort((left, right) => left.eventSequence - right.eventSequence);
    state.cachedTimelineSegments = entries.map((entry) => ({
        contentIndexBefore: entry.contentIndexBefore,
        eventSequence: entry.eventSequence,
        revisionSequence: entry.revisionSequence,
        segment: resolveActivitySegment(entry.segment, entry.revisionSequence)
    }));
    return state.cachedTimelineSegments;
};

const resolveActivitySegment = (segment: MessageSegment, revisionSequence: number): MessageSegment => {
    if (segment.type === 'image' || segment.type === 'inline_loading_activity' || segment.type === 'inline_processing_activity' || segment.type === 'inline_wait_for_user_activity') {
        return { ...segment, signatureSequence: revisionSequence };
    }
    return segment;
};

const resolveOrderedOverlayEntries = <TEntry>(cachedEntries: TEntry[] | null, sourceEntries: Iterable<TEntry>, getSequenceIndex: (entry: TEntry) => number, errorMessage: string, setCachedEntries: (entries: TEntry[]) => void): TEntry[] => {
    if (cachedEntries) {
        return cachedEntries;
    }
    const projected = Array.from(sourceEntries).sort((left, right) => getSequenceIndex(left) - getSequenceIndex(right));
    for (let index = 0; index < projected.length; index += 1) {
        const entry = projected[index];
        if (!entry || getSequenceIndex(entry) !== index) {
            throw new Error(errorMessage);
        }
    }
    setCachedEntries(projected);
    return projected;
};

const applyCollapsedOverrides = <TEntry extends { collapsed: boolean }>(baseEntries: TEntry[], overrides: Map<string, boolean>, getOverrideKey: (entry: TEntry) => string): TEntry[] => {
    if (baseEntries.length === 0 || overrides.size === 0) {
        return baseEntries;
    }
    return baseEntries.map((entry) => {
        const override = overrides.get(getOverrideKey(entry));
        if (override === undefined) {
            return entry;
        }
        return { ...entry, collapsed: override };
    });
};

const resolveToolActivity = (message: ChatMessage, state: AssistantTimelineIndexState): AssistantTimelineOverlays['toolActivity'] => {
    const base = resolveOrderedOverlayEntries(
        state.cachedToolActivity,
        state.toolActivityByCallId.values(),
        (entry) => entry.sequenceIndex,
        TOOL_SEQUENCE_INDEX_ERROR,
        (entries) => {
            state.cachedToolActivity = entries;
        }
    );
    if (base.length === 0) {
        return base;
    }
    const overrides = resolveCollapsedOverrideMap(message.inlineToolCollapsedByCallId);
    return applyCollapsedOverrides(base, overrides, (entry) => entry.callId);
};

const resolveThinkingTimeline = (message: ChatMessage, state: AssistantTimelineIndexState): AssistantTimelineOverlays['thinkingTimeline'] => {
    const base = resolveOrderedOverlayEntries(
        state.cachedThinkingTimeline,
        state.thinkingBySequenceIndex.values(),
        (entry) => entry.sequenceIndex,
        THINKING_SEQUENCE_INDEX_ERROR,
        (entries) => {
            state.cachedThinkingTimeline = entries;
        }
    );
    if (base.length === 0) {
        return base;
    }
    const overrides = resolveCollapsedOverrideMap(message.inlineThinkingCollapsedByCallId);
    return applyCollapsedOverrides(base, overrides, (entry) => entry.phaseId);
};

const resolveAssistantTimelineOverlays = (message: ChatMessage, state: AssistantTimelineIndexState): AssistantTimelineOverlays => {
    return {
        toolActivity: resolveToolActivity(message, state),
        thinkingTimeline: resolveThinkingTimeline(message, state)
    };
};

export { resolveAssistantTimelineActivitySegments, resolveAssistantTimelineOverlays, resolveCollapsedOverrideMap };
export type { AssistantTimelineIndexState };
