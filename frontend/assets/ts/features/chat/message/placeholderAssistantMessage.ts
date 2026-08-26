/* SoAI - Chat feature placeholder assistant message [frontend/assets/ts/features/chat/message/placeholderAssistantMessage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import { isJsonArray, isJsonObject } from '@core/types/jsonValues.ts';
import type { ChatContent, ChatMessage } from '@features/chat/ChatTypes.ts';
import { isAssistantMessageRole } from '@features/chat/message/messageRole.ts';

const isCancelledAssistantMessage = (message: ChatMessage): boolean => {
    if (!message || !isAssistantMessageRole(message)) {
        return false;
    }
    const finishReasonValue = message.finishReason;
    if (isString(finishReasonValue) && finishReasonValue.trim().toLowerCase() === 'cancelled') {
        return true;
    }
    const errorCodeValue = message.errorCode;
    if (!isString(errorCodeValue)) {
        return false;
    }
    const normalizedErrorCode = errorCodeValue.trim().toLowerCase();
    return normalizedErrorCode === 'cancelled';
};

const contentIsVisuallyEmpty = (content: ChatContent | undefined): boolean => {
    if (content === undefined || content === null) {
        return true;
    }
    if (isString(content)) {
        return content.trim().length === 0;
    }
    if (isJsonArray(content)) {
        if (content.length === 0) {
            return true;
        }
        return content.every((entry) => {
            if (entry === undefined || entry === null) {
                return true;
            }
            if (isString(entry)) {
                return entry.trim().length === 0;
            }
            if (!isJsonObject(entry)) {
                return false;
            }
            const typeValue = entry['type'];
            if (!isString(typeValue) || !typeValue.trim()) {
                return false;
            }
            const normalizedType = typeValue.trim().toLowerCase();
            if (normalizedType !== 'text' && normalizedType !== 'thinking') {
                return false;
            }
            const textValue = entry['text'];
            if (!isString(textValue)) {
                return false;
            }
            return textValue.trim().length === 0;
        });
    }
    if (isJsonObject(content)) {
        const typeValue = content['type'];
        if (!isString(typeValue) || !typeValue.trim()) {
            return false;
        }
        const normalizedType = typeValue.trim().toLowerCase();
        if (normalizedType !== 'text' && normalizedType !== 'thinking') {
            return false;
        }
        const textValue = content['text'];
        if (!isString(textValue)) {
            return false;
        }
        return textValue.trim().length === 0;
    }
    return false;
};

const isEmptyAssistantPlaceholderMessage = (message: ChatMessage): boolean => {
    if (!message || !isAssistantMessageRole(message)) {
        return false;
    }
    if (isCancelledAssistantMessage(message)) {
        return false;
    }
    const toolCallsValue = message.toolCalls;
    if (isJsonArray(toolCallsValue) && toolCallsValue.length > 0) {
        return false;
    }
    const timelineValue = message.assistantEventTimeline;
    if (isJsonArray(timelineValue) && timelineValue.some((entry) => Boolean(entry))) {
        return false;
    }
    const toolProjectionValue = message.toolCallProjections;
    if (isJsonArray(toolProjectionValue) && toolProjectionValue.some((entry) => Boolean(entry))) {
        return false;
    }
    return contentIsVisuallyEmpty(message.content);
};

export { isCancelledAssistantMessage, isEmptyAssistantPlaceholderMessage };
