/* SoAI - Context compaction boundary detection [frontend/assets/ts/features/chat/message/contextcompaction/detection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isBoolean, isString } from '@core/typeGuards.ts';
import { isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { AssistantEventTimelineItem, ChatMessage, SoaiCompactionMarker } from '@features/chat/ChatTypes.ts';
import { timelineHasVisibleAssistantTextDelta } from '@features/chat/assistanteventtimeline/timelineTextDeltas.ts';
import { flattenTextFragments } from '@features/chat/message/messageTextFlattening.ts';
import { normalizeToolLeafName } from '@features/chat/toolactivity/toolLeafName.ts';

const CONTEXT_COMPACTION_TOOL_LEAF = 'context_compaction';
const MANUAL_CONTEXT_COMPACTION_CALL_ID_PREFIX = `${CONTEXT_COMPACTION_TOOL_LEAF}:`;
const AUTO_CONTEXT_COMPACTION_CALL_ID_PREFIX = `${CONTEXT_COMPACTION_TOOL_LEAF}:auto:`;

const hasVisibleAssistantText = (message: ChatMessage): boolean => {
    return flattenTextFragments(message.content).join('').trim().length > 0 || timelineHasVisibleAssistantTextDelta(message.assistantEventTimeline);
};

const isManualContextCompactionCallId = (value: JsonValue | undefined): boolean => {
    if (!isString(value)) {
        return false;
    }
    const callId = value.trim();
    return callId.startsWith(MANUAL_CONTEXT_COMPACTION_CALL_ID_PREFIX) && !callId.startsWith(AUTO_CONTEXT_COMPACTION_CALL_ID_PREFIX);
};

const isManualContextCompactionMarker = (value: SoaiCompactionMarker | undefined): value is SoaiCompactionMarker => {
    if (!value) {
        return false;
    }
    const trigger = value.trigger;
    if (isString(trigger)) {
        return trigger.trim() === 'manual';
    }
    return isManualContextCompactionCallId(value.toolCallId ?? undefined);
};

const timelineHasManualContextCompactionActivity = (timeline: readonly AssistantEventTimelineItem[] | undefined): boolean => {
    if (!timeline) {
        return false;
    }
    for (const entry of timeline) {
        const tool = entry.payload.tool;
        if (tool === undefined) {
            continue;
        }
        if (normalizeToolLeafName(tool.toolName) !== CONTEXT_COMPACTION_TOOL_LEAF) {
            continue;
        }
        if (isManualContextCompactionCallId(tool.callId)) {
            return true;
        }
    }
    return false;
};

const hasManualContextCompactionBoundaryMarker = (message: ChatMessage): boolean => {
    return isManualContextCompactionMarker(message.soaiCompaction);
};

const isRemovedContextCompactionResult = (value: JsonValue | undefined): boolean => {
    if (!isJsonObject(value)) {
        return false;
    }
    const removedAtMs = value['boundary_removed_at_ms'];
    return typeof removedAtMs === 'number' && Number.isInteger(removedAtMs) && removedAtMs > 0;
};

const isContextCompactionBoundaryMessage = (message: ChatMessage): boolean => {
    if (message.role !== 'assistant' || hasVisibleAssistantText(message)) {
        return false;
    }
    return hasManualContextCompactionBoundaryMarker(message) || timelineHasManualContextCompactionActivity(message.assistantEventTimeline);
};

const isInactiveContextCompactionBoundaryMessage = (message: ChatMessage): boolean => {
    const marker = message.soaiCompaction;
    if (!isManualContextCompactionMarker(marker)) {
        return false;
    }
    const statusValue = marker.status;
    const isActiveBoundaryValue = marker.isActiveBoundary;
    return statusValue === 'completed' && isBoolean(isActiveBoundaryValue) && isActiveBoundaryValue === false;
};

const resolveContextCompactionRegenerationTimestamp = (message: ChatMessage): number | null => {
    const assistantTurnAtMs = message.assistantTurnAtMs;
    if (typeof assistantTurnAtMs === 'number' && Number.isInteger(assistantTurnAtMs) && assistantTurnAtMs > 0) {
        return assistantTurnAtMs;
    }
    const timestamp = message.timestamp;
    if (typeof timestamp === 'number' && Number.isInteger(timestamp) && timestamp > 0) {
        return timestamp;
    }
    return null;
};

export { CONTEXT_COMPACTION_TOOL_LEAF, hasManualContextCompactionBoundaryMarker, isContextCompactionBoundaryMessage, isInactiveContextCompactionBoundaryMessage, isManualContextCompactionCallId, isRemovedContextCompactionResult, resolveContextCompactionRegenerationTimestamp };
