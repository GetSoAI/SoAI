/* SoAI - Chat feature assistant response duration [frontend/assets/ts/features/chat/message/assistantResponseDuration.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNumber } from '@core/typeGuards.ts';
import { parseEpochMsOrNull } from '@core/time/epochMs.ts';
import type { ChatMessage, ToolActivityItem } from '@features/chat/ChatTypes.ts';
import { hasTerminalAssistantState } from '@features/chat/message/assistantTerminalState.ts';
import { CONTEXT_COMPACTION_TOOL_LEAF, isContextCompactionBoundaryMessage, isManualContextCompactionCallId } from '@features/chat/message/contextcompaction/detection.ts';
import { normalizeToolLeafName } from '@features/chat/toolactivity/toolLeafName.ts';

interface AssistantResponseDurationState {
    durationFloorMs: number | null;
    assistantStartedAtMs: number;
    completedAtMs: number | null;
    isSettled: boolean;
}

const resolveFiniteDurationMs = (value: number | null | undefined): number | null => {
    return isNumber(value) && Number.isFinite(value) && value >= 0 ? Math.floor(value) : null;
};

const requireAssistantStartedAtMs = (message: ChatMessage): number => {
    const startedAtMs = resolveFiniteDurationMs(message.assistantTurnAtMs);
    if (startedAtMs !== null) return startedAtMs;
    throw new Error('Assistant response duration requires assistantTurnAtMs');
};

const resolveManualCompactionActivity = (message: ChatMessage, tools: readonly ToolActivityItem[]): ToolActivityItem | null => {
    const callId = message.soaiCompaction?.toolCallId;
    const candidates = tools.filter((tool) => normalizeToolLeafName(tool.toolName) === CONTEXT_COMPACTION_TOOL_LEAF && isManualContextCompactionCallId(tool.callId));
    if (callId) return candidates.find((tool) => tool.callId === callId) ?? null;
    return candidates.length === 1 ? (candidates[0] ?? null) : null;
};

const resolveCompactionDurationState = (message: ChatMessage, nowMs: number, tools: readonly ToolActivityItem[]): AssistantResponseDurationState => {
    const activity = resolveManualCompactionActivity(message, tools);
    const startedAtMs = parseEpochMsOrNull(activity?.startedAtMs, 0);
    const completedAtMs = parseEpochMsOrNull(activity?.completedAtMs, 0);
    const isSettled = hasTerminalAssistantState(message) || activity?.status === 'completed' || activity?.status === 'cancelled' || activity?.status === 'error';
    const validCompletion = startedAtMs !== null && completedAtMs !== null && completedAtMs >= startedAtMs ? completedAtMs : null;
    const recordedDurationMs = resolveFiniteDurationMs(activity?.durationMs);
    const durationFloorMs = isSettled ? (recordedDurationMs ?? (validCompletion === null || startedAtMs === null ? null : validCompletion - startedAtMs)) : startedAtMs !== null && Number.isFinite(nowMs) ? Math.max(0, Math.floor(nowMs - startedAtMs)) : null;
    return {
        durationFloorMs,
        assistantStartedAtMs: startedAtMs ?? requireAssistantStartedAtMs(message),
        completedAtMs: validCompletion,
        isSettled
    };
};

const resolveAssistantResponseDurationState = (message: ChatMessage, nowMs: number, tools?: readonly ToolActivityItem[]): AssistantResponseDurationState => {
    if (isContextCompactionBoundaryMessage(message, tools)) return resolveCompactionDurationState(message, nowMs, tools ?? []);
    const isSettled = hasTerminalAssistantState(message);
    const assistantStartedAtMs = requireAssistantStartedAtMs(message);
    const durationFloorMs = isSettled ? resolveFiniteDurationMs(message.generationLatencyMs) : Number.isFinite(nowMs) ? Math.max(0, Math.floor(nowMs - assistantStartedAtMs)) : null;
    return {
        durationFloorMs,
        assistantStartedAtMs,
        completedAtMs: isSettled && durationFloorMs !== null ? parseEpochMsOrNull(assistantStartedAtMs + durationFloorMs, 0) : null,
        isSettled
    };
};

const resolveAssistantSettledResponseDisplayDurationMs = (message: ChatMessage, nowMs: number): number | null => {
    const state = resolveAssistantResponseDurationState(message, nowMs);
    return state.isSettled ? state.durationFloorMs : null;
};

export { resolveAssistantResponseDurationState, resolveAssistantSettledResponseDisplayDurationMs };
export type { AssistantResponseDurationState };
