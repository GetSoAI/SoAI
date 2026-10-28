/* SoAI - Chat feature assistant header duration [frontend/assets/ts/features/chat/message/messageview/assistantHeaderDuration.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { resolveAssistantResponseDurationState, type AssistantResponseDurationState } from '@features/chat/message/assistantResponseDuration.ts';
import { renderInlineActivityDurationMarkup, resolveInlineActivityDurationLabel, resolveInlineActivityDurationReserveCharacters, type InlineActivityDurationArguments } from '@features/chat/message/messageview/inlineActivityDuration.ts';

const resolveAssistantHeaderDurationArguments = (message: ChatMessage, nowMs: number, state: AssistantResponseDurationState = resolveAssistantResponseDurationState(message, nowMs)): InlineActivityDurationArguments | null => {
    if (state.durationFloorMs === null) {
        return null;
    }
    if (!state.isSettled) {
        return {
            status: 'running',
            durationMs: state.durationFloorMs,
            startedAtMs: state.assistantStartedAtMs,
            nowMs
        };
    }
    return {
        status: 'completed',
        durationMs: state.durationFloorMs
    };
};

const renderAssistantHeaderDuration = (escapeHtml: (value: string) => string, message: ChatMessage, nowMs: number, animateEntrance = false, state?: AssistantResponseDurationState): string => {
    const inputArguments = resolveAssistantHeaderDurationArguments(message, nowMs, state);
    if (inputArguments === null) {
        return '';
    }
    const label = resolveInlineActivityDurationLabel(inputArguments);
    if (label === null) {
        return '';
    }
    return renderInlineActivityDurationMarkup((value) => escapeHtml(value), label, {
        extraAttributes: ' data-assistant-response-duration="true"',
        reserveCharacters: resolveInlineActivityDurationReserveCharacters(inputArguments),
        animateEntrance
    });
};

export { renderAssistantHeaderDuration, resolveAssistantHeaderDurationArguments };
