/* SoAI - Chat feature conversation formatting [frontend/assets/ts/features/chat/conversationFormatting.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isNumber, isObject, isString } from '@core/typeGuards.ts';
import { stripSoaiPathTokensForDisplay } from '@core/soailinks/codec.ts';
import { CONVERSATION_TITLE_MAX_LENGTH } from '@features/chat/chatConstants.ts';
import type { ConversationContract } from '@features/chat/ChatTypes.ts';
import { resolveMessageTitle } from '@features/chat/messageBuilding.ts';

const calculateGenerationSpeed = (completionTokens: number | undefined, latencyMs: number): number | null => {
    if (typeof completionTokens !== 'number' || completionTokens <= 0 || latencyMs <= 0) {
        return null;
    }
    return Math.round((completionTokens / latencyMs) * 1000 * 100) / 100;
};

const sanitizeTitle = (title: string): string =>
    stripSoaiPathTokensForDisplay(title)
        .replace(/[\r\n]+/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();

const limitConversationTitleLength = (title: string): string => title.slice(0, CONVERSATION_TITLE_MAX_LENGTH);

const resolveConversationDisplayTitleFromConversation = (conversation: ConversationContract | null, defaultTitle: string): string => {
    if (conversation === null) {
        return defaultTitle;
    }
    if (isString(conversation.title)) {
        const stripped = sanitizeTitle(conversation.title);
        if (stripped) {
            return stripped;
        }
    }
    if (!isArray(conversation.messages)) {
        return defaultTitle;
    }
    for (const message of conversation.messages) {
        if (!isObject(message) || message['role'] !== 'user') {
            continue;
        }
        const messageTitle = resolveMessageTitle(message);
        if (messageTitle) {
            return messageTitle;
        }
    }
    return defaultTitle;
};

const formatTextZoomDisplay = (value: number): string => `${Math.round(value * 100)}%`;

const isConversationEmpty = (conversation: ConversationContract, defaultTitle: string): boolean => {
    const messages = conversation.messages;
    const title = conversation.title;
    const historyValue = conversation.history;
    const historyTotalCount = historyValue && isNumber(historyValue.totalCount) && Number.isFinite(historyValue.totalCount) ? historyValue.totalCount : null;
    const messageCountValue = conversation.messageCount;
    const persistedMessageCount = isNumber(messageCountValue) && Number.isFinite(messageCountValue) ? messageCountValue : null;
    const hasMessages = (historyTotalCount ?? persistedMessageCount ?? (isArray(messages) ? messages.length : 0)) > 0;
    const titleDisplay = isString(title) ? sanitizeTitle(title) : '';
    const hasCustomTitle = titleDisplay !== '' && titleDisplay !== defaultTitle;
    const isFavorite = conversation.isFavorite === true;
    const colorValue = conversation['color'];
    const hasColor = isString(colorValue) && colorValue.trim() !== '';
    return !hasMessages && !hasCustomTitle && !isFavorite && !hasColor;
};

const isProtectedEmptyConversation = (conversations: ReadonlyMap<string, ConversationContract>, conversationId: string, defaultTitle: string): boolean => {
    if (conversations.size !== 1) {
        return false;
    }
    const conversation = conversations.get(conversationId);
    if (!conversation) {
        return false;
    }
    return isConversationEmpty(conversation, defaultTitle);
};

export { calculateGenerationSpeed, formatTextZoomDisplay, isConversationEmpty, isProtectedEmptyConversation, limitConversationTitleLength, resolveConversationDisplayTitleFromConversation, sanitizeTitle };
