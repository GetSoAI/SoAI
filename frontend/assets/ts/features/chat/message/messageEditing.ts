/* SoAI - Chat feature message editing [frontend/assets/ts/features/chat/message/messageEditing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { isArray, isHTMLElement, isObject, isString } from '@core/typeGuards.ts';
import { isJsonObject } from '@core/types/jsonValues.ts';
import type { ChatContentSegment, ChatMessage } from '@features/chat/ChatTypes.ts';
import { normalizeMessageDomId } from '@features/chat/message/messageDomIds.ts';

export const resolveMessageContainer = (doc: Document, messageId: string): HTMLElement | null => {
    const normalizedId = normalizeMessageDomId(messageId);
    if (!normalizedId) {
        return null;
    }
    const candidates = dom.resolveAll('.chat-message', doc);
    for (const candidate of candidates) {
        if (!isHTMLElement(candidate)) {
            continue;
        }
        if (candidate.getAttribute('data-id') === normalizedId) {
            return candidate;
        }
    }
    return null;
};

export const readEditableUserText = (message: ChatMessage): string => {
    const content = message.content;
    if (isString(content)) {
        return content;
    }
    if (isArray(content)) {
        for (const part of content) {
            if (isString(part)) {
                return part;
            }
            if (part && isObject(part)) {
                const type = part['type'];
                if (type === 'text') {
                    const textValue = part['text'];
                    if (isString(textValue)) {
                        return textValue;
                    }
                    const valueValue = 'value' in part ? part.value : undefined;
                    if (isString(valueValue)) {
                        return valueValue;
                    }
                }
            }
        }
        return '';
    }
    if (content && isObject(content)) {
        const record = content;
        if (record['type'] === 'text') {
            const textValue = record['text'];
            if (isString(textValue)) {
                return textValue;
            }
            const valueValue = 'value' in record ? record.value : undefined;
            if (isString(valueValue)) {
                return valueValue;
            }
        }
    }
    return '';
};

export const applyEditedUserText = (message: ChatMessage, newText: string): void => {
    const content = message.content;
    if (isString(content)) {
        message.content = newText;
        return;
    }
    if (isArray(content)) {
        const parts = [...content];
        for (let index = 0; index < parts.length; index++) {
            const part = parts[index];
            if (isString(part)) {
                parts[index] = newText;
                message.content = parts;
                return;
            }
            if (part && isObject(part)) {
                if (part.type === 'text') {
                    parts[index] = { type: 'text', text: newText, value: newText };
                    message.content = parts;
                    return;
                }
            }
        }
        message.content = [{ type: 'text', text: newText }, ...parts];
        return;
    }
    if (content && isObject(content)) {
        if (content.type === 'text') {
            message.content = { type: 'text', text: newText, value: newText };
            return;
        }
    }
    message.content = [{ type: 'text', text: newText }];
};

const isEditableAttachmentContentPart = (value: ChatContentSegment): boolean => {
    if (!isJsonObject(value)) {
        return false;
    }
    const type = value['type'];
    return type === 'image' || type === 'image_url' || type === 'soai_file' || type === 'soai_path' || type === 'soai_knowledge' || type === 'soai_file_unavailable' || type === 'soai_knowledge_unavailable';
};

export const removeEditedUserAttachmentIndexes = (message: ChatMessage, removedAttachmentIndexes: readonly number[]): void => {
    if (!isArray(message.content) || removedAttachmentIndexes.length === 0) {
        return;
    }
    const removed = new Set(removedAttachmentIndexes);
    let attachmentIndex = 0;
    const nextContent: ChatContentSegment[] = [];
    for (const part of message.content) {
        if (isEditableAttachmentContentPart(part)) {
            if (!removed.has(attachmentIndex)) {
                nextContent.push(part);
            }
            attachmentIndex += 1;
            continue;
        }
        nextContent.push(part);
    }
    message.content = nextContent;
};

export const userMessageHasNonTextContent = (message: ChatMessage): boolean => {
    const content = message.content;
    if (!isArray(content)) {
        return Boolean(content && !isString(content));
    }
    for (const part of content) {
        if (isString(part)) {
            continue;
        }
        if (part && isObject(part)) {
            const type = part['type'];
            if (type !== 'text') {
                return true;
            }
            continue;
        }
        if (part !== null && part !== undefined) {
            return true;
        }
    }
    return false;
};
