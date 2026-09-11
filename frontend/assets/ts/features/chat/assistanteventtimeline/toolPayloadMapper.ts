/* SoAI - Chat feature tool payload mapper [frontend/assets/ts/features/chat/assistanteventtimeline/toolPayloadMapper.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { ToolActivityItem } from '@features/chat/ChatTypes.ts';
import { buildCanonicalSubagentToolResult } from '@features/chat/agent/agentSubagentToolResult.ts';
import { resolveToolActivityStatusRank } from '@features/chat/toolactivity/toolActivityStatus.ts';
import { normalizeToolLeafName } from '@features/chat/toolactivity/toolLeafName.ts';
import { decodeAssistantTimelineTool } from '@core/realtime/eventcontracts/assistantToolContracts.ts';
import type { AssistantTimelineTool } from '@core/realtime/eventcontracts/assistantTimelineTypes.ts';

const resolveDefined = <T>(existingValue: T | undefined, incomingValue: T | undefined): T | undefined => {
    if (incomingValue !== undefined) {
        return incomingValue;
    }
    return existingValue;
};

const resolvePreservedDefined = <T>(existingValue: T | undefined, incomingValue: T | undefined): T | undefined => {
    if (existingValue !== undefined) {
        return existingValue;
    }
    return incomingValue;
};

interface ToolActivityMergeOptions {
    replaceTerminalOutput: boolean;
    replaceLiveOutput: boolean;
}

const DEFAULT_TOOL_ACTIVITY_MERGE_OPTIONS: ToolActivityMergeOptions = {
    replaceTerminalOutput: false,
    replaceLiveOutput: false
};

const assertToolActivityChronologyMetadata = (existing: ToolActivityItem, incoming: ToolActivityItem): void => {
    if (existing.callId !== incoming.callId || existing.sequenceIndex !== incoming.sequenceIndex || existing.contentIndexBefore !== incoming.contentIndexBefore || existing.thinkingIndexBefore !== incoming.thinkingIndexBefore || existing.toolName !== incoming.toolName) {
        throw new Error(`Assistant event timeline call_id "${existing.callId}" contains inconsistent chronology metadata.`);
    }
};

const mapDecodedAssistantTimelineTool = (value: AssistantTimelineTool): ToolActivityItem => {
    const mapped: ToolActivityItem = {
        callId: value.callId,
        toolName: value.toolName,
        status: value.status,
        sequenceIndex: value.sequenceIndex,
        contentIndexBefore: value.contentIndexBefore,
        thinkingIndexBefore: value.thinkingIndexBefore,
        collapsed: value.collapsed
    };
    if (value.inputArguments !== undefined) mapped.inputArguments = value.inputArguments;
    if (value.result !== undefined) {
        const result = value.result;
        mapped.result = normalizeToolLeafName(mapped.toolName) === 'subagent_spawn' && isJsonObject(result) && isJsonObject(result['subagent']) ? buildCanonicalSubagentToolResult(result) : result;
    }
    if (value.error !== undefined) mapped.error = value.error;
    if (value.durationMs !== undefined) mapped.durationMs = value.durationMs;
    if (value.startedAtMs !== undefined) mapped.startedAtMs = value.startedAtMs;
    if (value.completedAtMs !== undefined) mapped.completedAtMs = value.completedAtMs;
    if (value.liveRevision !== undefined) mapped.liveRevision = value.liveRevision;
    if (value.lastLiveSequence !== undefined) mapped.lastLiveSequence = value.lastLiveSequence;
    if (value.lastLiveEventAtMs !== undefined) mapped.lastLiveEventAtMs = value.lastLiveEventAtMs;
    if (value.syncStatus !== undefined) mapped.syncStatus = value.syncStatus;
    if (value.thinkingDurationBeforeMs !== undefined) mapped.thinkingDurationBeforeMs = value.thinkingDurationBeforeMs;
    if (value.codeDiffs !== undefined) mapped.codeDiffs = value.codeDiffs;
    return mapped;
};

const mapAssistantTimelineToolPayload = (value: JsonValue | undefined): ToolActivityItem | null => {
    const decoded = decodeAssistantTimelineTool(value);
    return decoded === null ? null : mapDecodedAssistantTimelineTool(decoded);
};

const mergeToolActivityEntry = (existing: ToolActivityItem, incoming: ToolActivityItem, options: ToolActivityMergeOptions = DEFAULT_TOOL_ACTIVITY_MERGE_OPTIONS): ToolActivityItem => {
    assertToolActivityChronologyMetadata(existing, incoming);
    const existingStatusRank = resolveToolActivityStatusRank(existing.status);
    const incomingStatusRank = resolveToolActivityStatusRank(incoming.status);
    const mergedStatus = incomingStatusRank < existingStatusRank && !options.replaceTerminalOutput ? existing.status : incoming.status;

    const existingSignatureSequence = typeof existing.signatureSequence === 'number' && Number.isFinite(existing.signatureSequence) ? existing.signatureSequence : null;
    const incomingSignatureSequence = typeof incoming.signatureSequence === 'number' && Number.isFinite(incoming.signatureSequence) ? incoming.signatureSequence : null;
    const signatureSequence = existingSignatureSequence === null ? incomingSignatureSequence : incomingSignatureSequence === null ? existingSignatureSequence : Math.max(existingSignatureSequence, incomingSignatureSequence);

    const merged: ToolActivityItem = {
        callId: existing.callId,
        toolName: existing.toolName,
        status: mergedStatus,
        sequenceIndex: existing.sequenceIndex,
        contentIndexBefore: existing.contentIndexBefore,
        thinkingIndexBefore: existing.thinkingIndexBefore,
        collapsed: incoming.collapsed
    };
    if (signatureSequence !== null) {
        merged.signatureSequence = signatureSequence;
    }
    const mergedArguments = resolvePreservedDefined(existing.inputArguments, incoming.inputArguments);
    if (mergedArguments !== undefined) {
        merged.inputArguments = mergedArguments;
    }
    const mergedResult = options.replaceTerminalOutput || options.replaceLiveOutput ? incoming.result : resolvePreservedDefined(existing.result, incoming.result);
    if (mergedResult !== undefined) {
        merged.result = mergedResult;
    }
    const mergedError = options.replaceTerminalOutput ? incoming.error : resolvePreservedDefined(existing.error, incoming.error);
    if (mergedError !== undefined) {
        merged.error = mergedError;
    }
    const mergedDurationMs = resolveDefined(existing.durationMs, incoming.durationMs);
    if (mergedDurationMs !== undefined) {
        merged.durationMs = mergedDurationMs;
    }
    const mergedStartedAtMs = resolvePreservedDefined(existing.startedAtMs, incoming.startedAtMs);
    if (mergedStartedAtMs !== undefined) {
        merged.startedAtMs = mergedStartedAtMs;
    }
    const mergedCompletedAtMs = resolveDefined(existing.completedAtMs, incoming.completedAtMs);
    if (mergedCompletedAtMs !== undefined) {
        merged.completedAtMs = mergedCompletedAtMs;
    }
    const mergedLiveRevision = resolveDefined(existing.liveRevision, incoming.liveRevision);
    if (mergedLiveRevision !== undefined) {
        merged.liveRevision = mergedLiveRevision;
    }
    const mergedLastLiveSequence = resolveDefined(existing.lastLiveSequence, incoming.lastLiveSequence);
    if (mergedLastLiveSequence !== undefined) {
        merged.lastLiveSequence = mergedLastLiveSequence;
    }
    const mergedLastLiveEventAtMs = resolveDefined(existing.lastLiveEventAtMs, incoming.lastLiveEventAtMs);
    if (mergedLastLiveEventAtMs !== undefined) {
        merged.lastLiveEventAtMs = mergedLastLiveEventAtMs;
    }
    const mergedSyncStatus = resolveDefined(existing.syncStatus, incoming.syncStatus);
    if (mergedSyncStatus !== undefined) {
        merged.syncStatus = mergedSyncStatus;
    }
    const mergedThinkingDurationBeforeMs = resolveDefined(existing.thinkingDurationBeforeMs, incoming.thinkingDurationBeforeMs);
    if (mergedThinkingDurationBeforeMs !== undefined) {
        merged.thinkingDurationBeforeMs = mergedThinkingDurationBeforeMs;
    }
    const mergedCodeDiffs = resolveDefined(existing.codeDiffs, incoming.codeDiffs);
    if (mergedCodeDiffs !== undefined) {
        merged.codeDiffs = mergedCodeDiffs;
    }

    return merged;
};

export { assertToolActivityChronologyMetadata, mapAssistantTimelineToolPayload, mapDecodedAssistantTimelineTool, mergeToolActivityEntry };
