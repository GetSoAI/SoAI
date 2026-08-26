/* SoAI - Chat page persisted assistant timeline controller [frontend/assets/ts/pages/chat/controllers/chatpageagent/persistedAssistantTimelineController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray } from '@core/typeGuards.ts';
import { hasPersistedMessageId, hasTerminalAssistantState, isChatMessage, type ChatMessage, type Conversation } from '@features/chat/public.ts';

const hasAssistantTimeline = (message: ChatMessage): boolean => {
    const timeline = message.assistantEventTimeline;
    return isArray(timeline) && timeline.length > 0;
};

const isPersistedAuthoritativeAssistantMessage = (message: ChatMessage): boolean => {
    return hasPersistedMessageId(message) && (hasAssistantTimeline(message) || hasTerminalAssistantState(message));
};

const resolvePersistedAuthoritativeAssistantMessage = (conversation: Conversation | null): ChatMessage | null => {
    if (!conversation) {
        return null;
    }
    const { messages } = conversation;
    if (!isArray(messages) || messages.length === 0) {
        return null;
    }
    for (let index = messages.length - 1; index >= 0; index -= 1) {
        const message = messages[index];
        if (!isChatMessage(message) || message.role !== 'assistant') {
            continue;
        }
        if (!isPersistedAuthoritativeAssistantMessage(message)) {
            continue;
        }
        return message;
    }
    return null;
};

const hasPersistedAuthoritativeAssistantTimeline = (conversation: Conversation | null): boolean => {
    return resolvePersistedAuthoritativeAssistantMessage(conversation) !== null;
};

export { hasPersistedAuthoritativeAssistantTimeline, isPersistedAuthoritativeAssistantMessage, resolvePersistedAuthoritativeAssistantMessage };
