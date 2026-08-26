/* SoAI - Chat feature timeline index thinking updates [frontend/assets/ts/features/chat/assistanteventtimeline/timelineIndexThinkingUpdates.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AssistantTimelinePayload } from '@core/realtime/eventcontracts/assistantTimelineTypes.ts';
import { isTerminalAssistantActivityStatus } from '@features/chat/assistanteventtimeline/activityState.ts';
import { resolveChronologicalRenderAnchor } from '@features/chat/assistanteventtimeline/timelineChronology.ts';
import type { AssistantTimelineIndexState } from '@features/chat/assistanteventtimeline/timelineIndexState.ts';
import { validateSequenceIndexOwner } from '@features/chat/assistanteventtimeline/timelineSequenceIndexValidation.ts';
import type { ThinkingTimelineItem } from '@features/chat/ChatTypes.ts';

const THINKING_SEQUENCE_OWNER_ERROR = 'Assistant event timeline thinking_phase sequence_index cannot map to multiple phase_id values.';
const THINKING_SEQUENCE_CONTIGUOUS_ERROR = 'Assistant event timeline thinking_phase sequence_index values must be contiguous starting at 0.';

const resolveThinkingPayloadAnchor = (state: AssistantTimelineIndexState, phaseId: string, payloadAnchor: number, eventVisibleTextLength: number): number => {
    const resolvedPayloadAnchor = resolveChronologicalRenderAnchor(payloadAnchor, eventVisibleTextLength);
    const existingAnchor = state.thinkingRenderAnchorByPhaseId.get(phaseId);
    if (existingAnchor !== undefined) {
        if (resolvedPayloadAnchor !== existingAnchor) {
            throw new Error(`Assistant event timeline thinking_phase "${phaseId}" contains inconsistent chronology metadata.`);
        }
        return existingAnchor;
    }
    return resolvedPayloadAnchor;
};

const resolveRawThinkingPayloadAnchor = (state: AssistantTimelineIndexState, phaseId: string, anchorType: string, anchorPosition: number | undefined, anchorCallId: string | undefined): number | null => {
    if (anchorType === 'position') {
        if (anchorPosition === undefined) {
            throw new Error(`Thinking timeline phase ${phaseId} has invalid anchor_position`);
        }
        return anchorPosition;
    }
    if (anchorCallId === undefined || !anchorCallId.trim()) {
        throw new Error(`Thinking timeline phase ${phaseId} is missing anchor_call_id`);
    }
    const toolAnchor = state.toolRenderAnchorByCallId.get(anchorCallId.trim());
    if (toolAnchor === undefined) {
        if (state.hasTerminalEvent) {
            throw new Error(`Thinking timeline phase ${phaseId} references unknown anchor_call_id "${anchorCallId.trim()}".`);
        }
        return null;
    }
    return toolAnchor;
};

const assertThinkingPhaseChronologyMetadata = (existing: ThinkingTimelineItem, incoming: ThinkingTimelineItem): void => {
    if (existing.phaseId !== incoming.phaseId || existing.sequenceIndex !== incoming.sequenceIndex || existing.anchorType !== incoming.anchorType || existing.anchorPosition !== incoming.anchorPosition || existing.anchorCallId !== incoming.anchorCallId) {
        throw new Error(`Assistant event timeline thinking_phase "${existing.phaseId}" contains inconsistent chronology metadata.`);
    }
};

const applyThinkingPhaseUpdate = (state: AssistantTimelineIndexState, sequence: number, payload: AssistantTimelinePayload, eventVisibleTextLength: number): void => {
    const mapped = payload.thinkingPhase;
    if (mapped === undefined) {
        throw new Error('Assistant event timeline thinking_phase payload is invalid.');
    }

    const existingThinkingSequenceIndex = state.thinkingPhaseSequenceIndexByPhaseId.get(mapped.phaseId);
    if (existingThinkingSequenceIndex !== undefined && existingThinkingSequenceIndex !== mapped.sequenceIndex) {
        throw new Error(`Assistant event timeline thinking_phase "${mapped.phaseId}" contains inconsistent chronology metadata.`);
    }
    const existingThinking = state.thinkingBySequenceIndex.get(mapped.sequenceIndex);
    if (existingThinking !== undefined) {
        assertThinkingPhaseChronologyMetadata(existingThinking, mapped);
        if (isTerminalAssistantActivityStatus(existingThinking.status) && !isTerminalAssistantActivityStatus(mapped.status)) {
            throw new Error(`Assistant event timeline thinking_phase "${mapped.phaseId}" contains a regressed lifecycle status transition.`);
        }
    }
    validateSequenceIndexOwner(state.thinkingPhaseIdBySequenceIndex, mapped.sequenceIndex, mapped.phaseId, THINKING_SEQUENCE_OWNER_ERROR, THINKING_SEQUENCE_CONTIGUOUS_ERROR);

    if (existingThinkingSequenceIndex === undefined) {
        state.thinkingPhaseSequenceIndexByPhaseId.set(mapped.phaseId, mapped.sequenceIndex);
        state.thinkingSequenceByCallId.set(mapped.phaseId, sequence);
    }
    const rawAnchor = resolveRawThinkingPayloadAnchor(state, mapped.phaseId, mapped.anchorType, mapped.anchorPosition, mapped.anchorCallId);
    if (rawAnchor !== null) {
        state.thinkingRenderAnchorByPhaseId.set(mapped.phaseId, resolveThinkingPayloadAnchor(state, mapped.phaseId, rawAnchor, eventVisibleTextLength));
    }
    state.thinkingBySequenceIndex.set(mapped.sequenceIndex, { ...mapped, signatureSequence: sequence });
    state.cachedThinkingTimeline = null;
};

export { applyThinkingPhaseUpdate };
