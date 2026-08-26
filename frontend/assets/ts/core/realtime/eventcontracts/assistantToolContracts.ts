/* SoAI - Frontend assistant tool projection contracts [frontend/assets/ts/core/realtime/eventcontracts/assistantToolContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseOptionalCodeDiffArrayStrict } from '@core/chat/codeDiffParsing.ts';
import type { AssistantTimelineTool } from '@core/realtime/eventcontracts/assistantTimelineTypes.ts';
import { isBoolean, isNonNegativeInteger, isString } from '@core/typeGuards.ts';
import { isJsonObject, isJsonValue, type JsonValue } from '@core/types/jsonValues.ts';

const TOOL_STATUSES: ReadonlySet<string> = new Set(['pending', 'running', 'completed', 'cancelled', 'error']);
const isToolStatus = (value: string): value is AssistantTimelineTool['status'] => TOOL_STATUSES.has(value);

const optionalNonNegativeInteger = (record: Record<string, JsonValue | undefined>, key: string): number | null | undefined => {
    const value = record[key];
    if (value === undefined || value === null) return value;
    return isNonNegativeInteger(value) ? value : undefined;
};

const hasInvalidOptionalInteger = (record: Record<string, JsonValue | undefined>, key: string, decoded: number | null | undefined): boolean => decoded === undefined && record[key] !== undefined && record[key] !== null;

const decodeAssistantTimelineTool = (value: JsonValue | null | undefined): AssistantTimelineTool | null => {
    if (!isJsonObject(value)) return null;
    const callId = value['call_id'];
    const toolName = value['tool_name'];
    const status = value['status'];
    const sequenceIndex = value['sequence_index'];
    const messageIndex = value['message_index'];
    const contentIndexBefore = value['content_index_before'];
    const thinkingIndexBefore = value['thinking_index_before'];
    const collapsed = value['collapsed'];
    if (!isString(callId) || !callId.trim() || !isString(toolName) || !toolName.trim()) return null;
    if (!isString(status) || !isToolStatus(status)) return null;
    if (!isNonNegativeInteger(sequenceIndex) || !isNonNegativeInteger(messageIndex) || !isNonNegativeInteger(contentIndexBefore) || !isNonNegativeInteger(thinkingIndexBefore) || !isBoolean(collapsed)) return null;
    const decoded: AssistantTimelineTool = { callId: callId.trim(), toolName: toolName.trim(), status, sequenceIndex, messageIndex, contentIndexBefore, thinkingIndexBefore, collapsed };
    if (value['arguments'] !== undefined) {
        if (!isJsonValue(value['arguments'])) return null;
        decoded.inputArguments = value['arguments'];
    }
    if (value['result'] !== undefined) {
        if (!isJsonValue(value['result'])) return null;
        decoded.result = value['result'];
    }
    const error = value['error'];
    if (error !== undefined && error !== null) {
        if (!isString(error)) return null;
        decoded.error = error;
    }
    const durationMs = optionalNonNegativeInteger(value, 'duration_ms');
    const startedAtMs = optionalNonNegativeInteger(value, 'started_at_ms');
    const completedAtMs = optionalNonNegativeInteger(value, 'completed_at_ms');
    const liveRevision = optionalNonNegativeInteger(value, 'live_revision');
    const lastLiveSequence = optionalNonNegativeInteger(value, 'last_live_sequence');
    const lastLiveEventAtMs = optionalNonNegativeInteger(value, 'last_live_event_at_ms');
    const thinkingDurationBeforeMs = optionalNonNegativeInteger(value, 'thinking_duration_before_ms');
    const assistantTurnAtMs = optionalNonNegativeInteger(value, 'assistant_turn_at_ms');
    const modelVariantIndex = optionalNonNegativeInteger(value, 'model_variant_index');
    const iterationIndex = optionalNonNegativeInteger(value, 'iteration_index');
    if (hasInvalidOptionalInteger(value, 'duration_ms', durationMs) || hasInvalidOptionalInteger(value, 'started_at_ms', startedAtMs) || hasInvalidOptionalInteger(value, 'completed_at_ms', completedAtMs) || hasInvalidOptionalInteger(value, 'live_revision', liveRevision) || hasInvalidOptionalInteger(value, 'last_live_sequence', lastLiveSequence) || hasInvalidOptionalInteger(value, 'last_live_event_at_ms', lastLiveEventAtMs) || hasInvalidOptionalInteger(value, 'thinking_duration_before_ms', thinkingDurationBeforeMs) || hasInvalidOptionalInteger(value, 'assistant_turn_at_ms', assistantTurnAtMs) || hasInvalidOptionalInteger(value, 'model_variant_index', modelVariantIndex) || hasInvalidOptionalInteger(value, 'iteration_index', iterationIndex)) return null;
    if (durationMs !== undefined && durationMs !== null) decoded.durationMs = durationMs;
    if (startedAtMs !== undefined && startedAtMs !== null) decoded.startedAtMs = startedAtMs;
    if (completedAtMs !== undefined && completedAtMs !== null) decoded.completedAtMs = completedAtMs;
    if (liveRevision !== undefined && liveRevision !== null) decoded.liveRevision = liveRevision;
    if (lastLiveSequence !== undefined && lastLiveSequence !== null) decoded.lastLiveSequence = lastLiveSequence;
    if (lastLiveEventAtMs !== undefined && lastLiveEventAtMs !== null) decoded.lastLiveEventAtMs = lastLiveEventAtMs;
    if (thinkingDurationBeforeMs !== undefined && thinkingDurationBeforeMs !== null) decoded.thinkingDurationBeforeMs = thinkingDurationBeforeMs;
    if (assistantTurnAtMs !== undefined && assistantTurnAtMs !== null) decoded.assistantTurnAtMs = assistantTurnAtMs;
    if (modelVariantIndex !== undefined && modelVariantIndex !== null) decoded.modelVariantIndex = modelVariantIndex;
    if (iterationIndex !== undefined && iterationIndex !== null) decoded.iterationIndex = iterationIndex;
    const turnId = value['turn_id'];
    if (turnId !== undefined && turnId !== null) {
        if (!isString(turnId) || !turnId.trim()) return null;
        decoded.turnId = turnId.trim();
    }
    const syncStatus = value['sync_status'];
    if (syncStatus !== undefined && syncStatus !== null) {
        if (syncStatus !== 'in_sync' && syncStatus !== 'out_of_sync') return null;
        decoded.syncStatus = syncStatus;
    }
    const codeDiffs = parseOptionalCodeDiffArrayStrict(value['code_diffs']);
    if (codeDiffs === null) return null;
    if (codeDiffs !== undefined && codeDiffs.length > 0) decoded.codeDiffs = codeDiffs;
    return decoded;
};

const requireAssistantTimelineTool = (value: JsonValue | null | undefined, label: string): AssistantTimelineTool => {
    const decoded = decodeAssistantTimelineTool(value);
    if (decoded === null) throw new TypeError(`${label} must be a canonical tool projection`);
    return decoded;
};

export { decodeAssistantTimelineTool, requireAssistantTimelineTool };
