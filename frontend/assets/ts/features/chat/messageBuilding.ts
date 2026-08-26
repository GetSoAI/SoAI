/* SoAI - Chat message construction helpers [frontend/assets/ts/features/chat/messageBuilding.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { stripSoaiPathTokensForDisplay } from '@core/soailinks/codec.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isInstanceOf, isObject, isString } from '@core/typeGuards.ts';
import type { ChatContentSegment, ConversationMessage } from '@features/chat/ChatTypes.ts';

export const isRagDocumentAttachment = (attachment: JsonValue | null | undefined): boolean => {
    if (!isObject(attachment)) {
        return false;
    }
    if (attachment['is_image'] === true) {
        return false;
    }
    return isString(attachment['rag_document_id']);
};

export const isReadyRagDocumentAttachment = (attachment: JsonValue | null | undefined): boolean => {
    if (!isRagDocumentAttachment(attachment)) {
        return false;
    }
    if (!isObject(attachment)) {
        return false;
    }
    return attachment['parse_status'] === 'ready';
};

export const buildUserMessageContent = (messageText: string, attachmentContent: readonly ChatContentSegment[]): ChatContentSegment[] => {
    const content: ChatContentSegment[] = [];
    if (messageText) {
        content.push({ type: 'text', text: messageText });
    }
    if (attachmentContent.length > 0) {
        for (const fragment of attachmentContent) {
            if (!isObject(fragment) || isString(fragment)) {
                throw new Error('User message attachment fragment must be an object.');
            }
            const typeValue = fragment.type;
            const fragmentType = toTrimmedString(typeValue);
            if (!fragmentType) {
                throw new Error('User message attachment fragment must include a non-empty type.');
            }
            content.push(fragment);
        }
    }
    return content;
};

export const resolveMessageTitle = (message: ConversationMessage, maxLength = 50): string => {
    if (!isObject(message)) {
        return '';
    }
    const messageContent = message['content'];
    let text = '';
    if (isArray(messageContent)) {
        for (const entry of messageContent) {
            if (!isObject(entry)) {
                continue;
            }
            if (entry['type'] !== 'text') {
                continue;
            }
            const entryText = entry['text'];
            if (isString(entryText)) {
                text = entryText;
                break;
            }
        }
    } else if (isString(messageContent)) {
        text = messageContent;
    }
    const trimmed = stripSoaiPathTokensForDisplay(text).trim();
    if (trimmed) {
        return trimmed.length > maxLength ? trimmed.substring(0, maxLength - 3) + '...' : trimmed;
    }
    if (!isArray(messageContent)) {
        return '';
    }
    for (const entry of messageContent) {
        if (!isObject(entry) || entry['type'] !== 'soai_path') {
            continue;
        }
        const titleValue = entry['title'];
        const attachmentTitle = isString(titleValue) ? titleValue.trim() : '';
        if (attachmentTitle) {
            return attachmentTitle.length > maxLength ? attachmentTitle.substring(0, maxLength - 3) + '...' : attachmentTitle;
        }
    }
    for (const entry of messageContent) {
        if (!isObject(entry) || entry['type'] !== 'soai_file') {
            continue;
        }
        const filenameValue = entry['filename'];
        const filename = isString(filenameValue) ? filenameValue.trim() : '';
        if (filename) {
            return filename.length > maxLength ? filename.substring(0, maxLength - 3) + '...' : filename;
        }
    }
    let imageCount = 0;
    for (const entry of messageContent) {
        if (!isObject(entry) || entry['type'] !== 'image_url') {
            continue;
        }
        imageCount += 1;
    }
    if (imageCount === 1) {
        return i18n.t('chat.conversation.defaultTitleImage');
    }
    if (imageCount > 1) {
        return i18n.t('chat.conversation.defaultTitleImages', { count: imageCount });
    }
    return '';
};

export const resolveUploadFilesFromEvent = (event: Event): File[] => {
    if (!isInstanceOf(event.target, HTMLInputElement)) {
        throw new Error('Upload input event target is not a file input');
    }
    const input = event.target;
    const fileList = input.files;
    const files = fileList ? [...fileList] : [];
    input.value = '';
    return files;
};

export const normalizeFolderUploadFiles = (files: File[]): File[] => {
    if (!isArray(files)) {
        throw new Error('Upload files must be an array');
    }
    return files.map((file) => {
        const candidate = isObject(file) ? file : null;
        const relativePath = candidate ? candidate['webkitRelativePath'] : null;
        if (!isString(relativePath) || !relativePath.trim() || relativePath.trim() === file.name) {
            return file;
        }
        return new File([file], relativePath.trim(), { type: file.type, lastModified: file.lastModified });
    });
};

export const hasFolderUploadFiles = (files: File[]): boolean => {
    if (!isArray(files)) {
        throw new Error('Upload files must be an array');
    }
    return files.some((file) => {
        const candidate = isObject(file) ? file : null;
        const relativePath = candidate ? candidate['webkitRelativePath'] : null;
        return isString(relativePath) && relativePath.trim().length > 0 && relativePath.trim() !== file.name;
    });
};
