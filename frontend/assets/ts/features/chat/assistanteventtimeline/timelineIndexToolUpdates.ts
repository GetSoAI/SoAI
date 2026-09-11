/* SoAI - Chat feature timeline index tool updates [frontend/assets/ts/features/chat/assistanteventtimeline/timelineIndexToolUpdates.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AssistantTimelinePayload } from '@core/realtime/eventcontracts/assistantTimelineTypes.ts';
import { resolveChronologicalRenderAnchor } from '@features/chat/assistanteventtimeline/timelineChronology.ts';
import { assertToolActivityChronologyMetadata, mapDecodedAssistantTimelineTool, mergeToolActivityEntry } from '@features/chat/assistanteventtimeline/toolPayloadMapper.ts';
import type { AssistantTimelineIndexState, ToolActivitySource } from '@features/chat/assistanteventtimeline/timelineIndexState.ts';
import type { ToolActivityItem } from '@features/chat/ChatTypes.ts';
import { validateSequenceIndexOwner, validateSparseSequenceIndexOwner } from '@features/chat/assistanteventtimeline/timelineSequenceIndexValidation.ts';
import { shouldReplaceToolProjection } from '@features/chat/toolactivity/toolProjectionFreshness.ts';
import { isTerminalToolActivityStatus, resolveToolActivityStatusRank } from '@features/chat/toolactivity/toolActivityStatus.ts';
import { mergeHydratedToolResultIntoProjection } from '@features/chat/toolactivity/toolProjectionMutation.ts';

const TOOL_SEQUENCE_OWNER_ERROR = 'Assistant event timeline tool sequence_index cannot map to multiple call_id values.';
const TOOL_SEQUENCE_CONTIGUOUS_ERROR = 'Assistant event timeline tool sequence_index values must be contiguous starting at 0.';

interface ToolProjectionApplyResult {
    callId: string;
    source: ToolActivitySource;
}

const TOOL_SOURCE_STATE_ERROR = 'Assistant event timeline tool source state is inconsistent.';

const resolveToolActivitySource = (state: AssistantTimelineIndexState, callId: string, existing: ToolActivityItem | undefined): ToolActivitySource | undefined => {
    const source = state.toolSourceByCallId.get(callId);
    if ((existing === undefined) !== (source === undefined)) {
        throw new Error(TOOL_SOURCE_STATE_ERROR);
    }
    if (source === 'lifecycle' && !state.toolLifecycleStatusRankByCallId.has(callId)) {
        throw new Error(TOOL_SOURCE_STATE_ERROR);
    }
    if (source === 'projection' && state.toolLifecycleStatusRankByCallId.has(callId)) {
        throw new Error(TOOL_SOURCE_STATE_ERROR);
    }
    return source;
};

const applyProjectionMediaHydration = (state: AssistantTimelineIndexState, existing: ToolActivityItem, mapped: ToolActivityItem): void => {
    const mediaHydrated = mergeHydratedToolResultIntoProjection(existing, mapped);
    if (mediaHydrated !== null) {
        state.toolActivityByCallId.set(mapped.callId, mediaHydrated);
        state.cachedToolActivity = null;
    }
};

const isDurationOnlyProjectionUpdate = (existing: ToolActivityItem, incoming: ToolActivityItem): boolean => {
    if (existing.status !== 'running' || incoming.status !== 'running') {
        return false;
    }
    if (existing.callId !== incoming.callId || existing.toolName !== incoming.toolName || existing.sequenceIndex !== incoming.sequenceIndex || existing.contentIndexBefore !== incoming.contentIndexBefore || existing.thinkingIndexBefore !== incoming.thinkingIndexBefore || existing.collapsed !== incoming.collapsed || existing.startedAtMs !== incoming.startedAtMs || existing.completedAtMs !== incoming.completedAtMs || existing.thinkingDurationBeforeMs !== incoming.thinkingDurationBeforeMs || existing.error !== incoming.error) {
        return false;
    }
    if (existing.inputArguments !== incoming.inputArguments || existing.codeDiffs !== incoming.codeDiffs || existing.result !== incoming.result) {
        return false;
    }
    return existing.durationMs !== incoming.durationMs || existing.liveRevision !== incoming.liveRevision || existing.lastLiveSequence !== incoming.lastLiveSequence || existing.lastLiveEventAtMs !== incoming.lastLiveEventAtMs || existing.syncStatus !== incoming.syncStatus;
};

const applyDurationOnlyProjectionMutation = (target: ToolActivityItem, source: ToolActivityItem, signatureSequence: number): void => {
    if (source.durationMs === undefined) {
        delete target.durationMs;
    } else {
        target.durationMs = source.durationMs;
    }
    if (source.liveRevision === undefined) {
        delete target.liveRevision;
    } else {
        target.liveRevision = source.liveRevision;
    }
    if (source.lastLiveSequence === undefined) {
        delete target.lastLiveSequence;
    } else {
        target.lastLiveSequence = source.lastLiveSequence;
    }
    if (source.lastLiveEventAtMs === undefined) {
        delete target.lastLiveEventAtMs;
    } else {
        target.lastLiveEventAtMs = source.lastLiveEventAtMs;
    }
    if (source.syncStatus === undefined) {
        delete target.syncStatus;
    } else {
        target.syncStatus = source.syncStatus;
    }
    target.signatureSequence = signatureSequence;
};

const resolveProjectionOnlyToolSequence = (state: AssistantTimelineIndexState, mapped: ToolActivityItem): number => {
    if (state.processedLength <= 0) {
        return mapped.sequenceIndex;
    }
    return state.processedLength + mapped.sequenceIndex;
};

const resolveStableToolRenderAnchor = (state: AssistantTimelineIndexState, mapped: ToolActivityItem, eventVisibleTextLength: number): number => {
    const existingAnchor = state.toolRenderAnchorByCallId.get(mapped.callId);
    if (existingAnchor !== undefined) {
        resolveChronologicalRenderAnchor(mapped.contentIndexBefore, eventVisibleTextLength);
        return existingAnchor;
    }
    return resolveChronologicalRenderAnchor(mapped.contentIndexBefore, eventVisibleTextLength);
};

const copyToolActivityWithRenderAnchor = (mapped: ToolActivityItem, contentIndexBefore: number): ToolActivityItem => {
    return { ...mapped, contentIndexBefore: contentIndexBefore };
};

const applyToolCallLifecycleUpdate = (state: AssistantTimelineIndexState, sequence: number, payload: AssistantTimelinePayload, eventType: string, eventVisibleTextLength: number): boolean => {
    if (payload.tool === undefined) {
        throw new Error(`Assistant event timeline ${eventType} payload is invalid.`);
    }
    const rawMapped = mapDecodedAssistantTimelineTool(payload.tool);
    const mapped = copyToolActivityWithRenderAnchor(rawMapped, resolveStableToolRenderAnchor(state, rawMapped, eventVisibleTextLength));
    mapped.signatureSequence = sequence;

    const existing = state.toolActivityByCallId.get(mapped.callId);
    resolveToolActivitySource(state, mapped.callId, existing);
    if (existing !== undefined) {
        assertToolActivityChronologyMetadata(existing, mapped);
    }
    const previousLifecycleStatusRank = state.toolLifecycleStatusRankByCallId.get(mapped.callId);
    const incomingLifecycleStatusRank = resolveToolActivityStatusRank(mapped.status);
    if (previousLifecycleStatusRank !== undefined && incomingLifecycleStatusRank < previousLifecycleStatusRank) {
        throw new Error(`Assistant event timeline call_id "${mapped.callId}" contains a regressed tool lifecycle status transition.`);
    }
    const insertedNewToolSegment = previousLifecycleStatusRank === undefined;
    const merged = existing
        ? mergeToolActivityEntry(existing, mapped, {
              replaceTerminalOutput: isTerminalToolActivityStatus(mapped.status),
              replaceLiveOutput: false
          })
        : mapped;
    merged.signatureSequence = sequence;

    validateSequenceIndexOwner(state.toolCallIdBySequenceIndex, mapped.sequenceIndex, mapped.callId, TOOL_SEQUENCE_OWNER_ERROR, TOOL_SEQUENCE_CONTIGUOUS_ERROR);
    if (insertedNewToolSegment) {
        state.toolRenderSequenceByCallId.set(mapped.callId, sequence);
    }
    state.toolSourceByCallId.set(mapped.callId, 'lifecycle');
    state.toolLifecycleStatusRankByCallId.set(mapped.callId, incomingLifecycleStatusRank);
    state.toolRenderAnchorByCallId.set(mapped.callId, mapped.contentIndexBefore);
    state.toolActivityByCallId.set(mapped.callId, merged);
    state.cachedToolActivity = null;
    return insertedNewToolSegment;
};

const applyToolCallProjectionUpdate = (state: AssistantTimelineIndexState, payload: ToolActivityItem, eventVisibleTextLength: number): ToolProjectionApplyResult => {
    const mapped = copyToolActivityWithRenderAnchor(payload, resolveStableToolRenderAnchor(state, payload, eventVisibleTextLength));
    const revision = typeof mapped.liveRevision === 'number' && Number.isFinite(mapped.liveRevision) ? mapped.liveRevision : 0;
    mapped.signatureSequence = revision;
    const existing = state.toolActivityByCallId.get(mapped.callId);
    const source = resolveToolActivitySource(state, mapped.callId, existing);
    if (existing !== undefined) {
        assertToolActivityChronologyMetadata(existing, mapped);
    }
    const insertedNewToolSegment = !state.toolRenderSequenceByCallId.has(mapped.callId);
    if (existing !== undefined) {
        if (source === undefined) {
            throw new Error(TOOL_SOURCE_STATE_ERROR);
        }
        if (source === 'lifecycle' && isTerminalToolActivityStatus(existing.status)) {
            applyProjectionMediaHydration(state, existing, mapped);
            return { callId: mapped.callId, source };
        }
        if (!shouldReplaceToolProjection(existing, mapped)) {
            applyProjectionMediaHydration(state, existing, mapped);
            return { callId: mapped.callId, source };
        }
    }
    const durationOnlyProjectionUpdate = existing !== undefined && isDurationOnlyProjectionUpdate(existing, mapped);
    const replaceLiveOutput = existing !== undefined && existing.status === 'running' && mapped.status === 'running' && mapped.result !== undefined;
    const baseMerged =
        existing && !durationOnlyProjectionUpdate
            ? mergeToolActivityEntry(existing, mapped, {
                  replaceTerminalOutput: false,
                  replaceLiveOutput
              })
            : mapped;
    const merged = existing === undefined ? baseMerged : (mergeHydratedToolResultIntoProjection(baseMerged, mapped) ?? baseMerged);
    merged.signatureSequence = revision;

    validateSparseSequenceIndexOwner(state.toolCallIdBySequenceIndex, mapped.sequenceIndex, mapped.callId, TOOL_SEQUENCE_OWNER_ERROR);
    if (insertedNewToolSegment) {
        state.toolRenderSequenceByCallId.set(mapped.callId, resolveProjectionOnlyToolSequence(state, mapped));
    }
    if (existing === undefined) {
        state.toolSourceByCallId.set(mapped.callId, 'projection');
    }
    state.toolRenderAnchorByCallId.set(mapped.callId, mapped.contentIndexBefore);
    if (existing && durationOnlyProjectionUpdate) {
        applyDurationOnlyProjectionMutation(existing, mapped, revision);
        state.cachedToolActivity = null;
        return { callId: mapped.callId, source: source ?? 'projection' };
    }
    state.toolActivityByCallId.set(mapped.callId, merged);
    state.cachedToolActivity = null;
    return { callId: mapped.callId, source: source ?? 'projection' };
};

export { applyToolCallLifecycleUpdate, applyToolCallProjectionUpdate };
