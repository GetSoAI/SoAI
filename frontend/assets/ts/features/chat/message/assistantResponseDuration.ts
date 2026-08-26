/* SoAI - Chat feature assistant response duration [frontend/assets/ts/features/chat/message/assistantResponseDuration.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNumber } from '@core/typeGuards.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { hasTerminalAssistantState } from '@features/chat/message/assistantTerminalState.ts';

interface AssistantResponseDurationState {
    durationFloorMs: number | null;
    assistantStartedAtMs: number;
    isSettled: boolean;
}

const resolveFiniteDurationMs = (value: number | null | undefined): number | null => {
    if (!isNumber(value) || !Number.isFinite(value) || value < 0) {
        return null;
    }
    return Math.floor(value);
};

const requireAssistantStartedAtMs = (message: ChatMessage): number => {
    const assistantTurnStartedAtMs = resolveFiniteDurationMs(message.assistantTurnAtMs);
    if (assistantTurnStartedAtMs !== null) {
        return assistantTurnStartedAtMs;
    }
    throw new Error('Assistant response duration requires assistantTurnAtMs');
};

const resolveAssistantResponseDurationState = (message: ChatMessage, nowMs: number): AssistantResponseDurationState => {
    const hasTerminalState = hasTerminalAssistantState(message);
    const assistantStartedAtMs = requireAssistantStartedAtMs(message);
    const persistedDurationMs = resolveFiniteDurationMs(message.generationLatencyMs);
    const liveDurationMs = Number.isFinite(nowMs) ? Math.max(0, Math.floor(nowMs - assistantStartedAtMs)) : null;
    const durationFloorMs = hasTerminalState ? (persistedDurationMs ?? liveDurationMs) : liveDurationMs;

    return {
        durationFloorMs,
        assistantStartedAtMs,
        isSettled: hasTerminalState
    };
};

const resolveAssistantSettledResponseDisplayDurationMs = (message: ChatMessage, nowMs: number): number | null => {
    const state = resolveAssistantResponseDurationState(message, nowMs);
    if (!state.isSettled || state.durationFloorMs === null) {
        return null;
    }
    return state.durationFloorMs;
};

export { resolveAssistantResponseDurationState, resolveAssistantSettledResponseDisplayDurationMs };
