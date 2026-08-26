/* SoAI - Shared assistant terminal state resolution [frontend/assets/ts/features/chat/message/assistantTerminalState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { optionalTrimmedString } from '@core/types/payloadValueReaders.ts';
import { resolveLatestLoadingActivityFromMessage } from '@features/chat/assistanteventtimeline/activityState.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';

type AssistantTerminalState = 'complete' | 'cancelled' | 'error';

const resolveAssistantTerminalState = (message: ChatMessage | null | undefined): AssistantTerminalState | null => {
    if (!message) {
        return null;
    }
    const finishReason = optionalTrimmedString(message.finishReason);
    if (finishReason === 'cancelled') {
        return 'cancelled';
    }
    if (finishReason === 'error') {
        return 'error';
    }
    if (finishReason !== null) {
        return 'complete';
    }
    if (optionalTrimmedString(message.errorCode) !== null) {
        return 'error';
    }
    return null;
};

const resolveTimelineTerminalState = (message: ChatMessage): AssistantTerminalState | null => {
    const timeline = message.assistantEventTimeline;
    if (!timeline) {
        return null;
    }
    for (let index = timeline.length - 1; index >= 0; index -= 1) {
        const event = timeline[index];
        if (!event) {
            continue;
        }
        const eventType = optionalTrimmedString(event.eventType);
        if (eventType === 'completed') {
            return 'complete';
        }
        if (eventType === 'cancelled') {
            return 'cancelled';
        }
        if (eventType === 'error') {
            return 'error';
        }
    }
    return null;
};

const resolveDurableAssistantTerminalState = (message: ChatMessage): AssistantTerminalState | null => {
    const explicitTerminalState = resolveAssistantTerminalState(message);
    if (explicitTerminalState !== null) {
        return explicitTerminalState;
    }
    return resolveTimelineTerminalState(message);
};

const resolveHydratedAssistantTerminalState = (message: ChatMessage): AssistantTerminalState | null => {
    const durableTerminalState = resolveDurableAssistantTerminalState(message);
    if (durableTerminalState !== null) {
        return durableTerminalState;
    }
    const loadingActivity = resolveLatestLoadingActivityFromMessage(message);
    if (loadingActivity === null) {
        return null;
    }
    if (loadingActivity.status === 'cancelled') {
        return 'cancelled';
    }
    if (loadingActivity.status === 'error') {
        return 'error';
    }
    return null;
};

const hasTerminalAssistantState = (message: ChatMessage): boolean => {
    return resolveDurableAssistantTerminalState(message) !== null;
};

export { hasTerminalAssistantState, resolveAssistantTerminalState, resolveDurableAssistantTerminalState, resolveHydratedAssistantTerminalState };
export type { AssistantTerminalState };
