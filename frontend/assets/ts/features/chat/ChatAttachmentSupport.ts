/* SoAI - Chat feature attachment support [frontend/assets/ts/features/chat/ChatAttachmentSupport.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import { isImageMimeType } from '@core/media/mimeTypes.ts';
import { isSoaiFileAttachmentReadyForSend } from '@features/chat/attachments/soaiFileContentPart.ts';
import { isSoaiPathDraftRecord } from '@features/chat/attachments/soaiPathDraftRecords.ts';
import type { ChatAttachment } from '@features/chat/ChatTypes.ts';

const getFileExtension = (name: string | null | undefined): string | null => {
    if (!isString(name)) return null;
    const index = name.lastIndexOf('.');
    if (index < 0 || index === name.length - 1) {
        return null;
    }
    return name.slice(index + 1).toLowerCase();
};

const resolveMimeTypeGuessFromExtension = (extension: string): string | null => {
    const normalized = extension.trim().toLowerCase();
    if (!normalized) {
        return null;
    }
    if (normalized === 'jpg' || normalized === 'jpeg') return 'image/jpeg';
    if (normalized === 'png') return 'image/png';
    if (normalized === 'gif') return 'image/gif';
    if (normalized === 'webp') return 'image/webp';
    if (normalized === 'bmp') return 'image/bmp';
    if (normalized === 'heic') return 'image/heic';
    if (normalized === 'heif') return 'image/heif';
    if (normalized === 'pdf') return 'application/pdf';
    if (normalized === 'txt') return 'text/plain';
    if (normalized === 'md' || normalized === 'markdown') return 'text/markdown';
    if (normalized === 'csv') return 'text/csv';
    if (normalized === 'json') return 'application/json';
    if (normalized === 'xml') return 'application/xml';
    return null;
};

const isSupportedChatImageFile = (file: { type?: string | null; name?: string | null } | null | undefined): boolean => {
    if (!file) {
        return false;
    }
    const typeValue = file.type;
    const normalizedType = isString(typeValue) ? typeValue.trim().toLowerCase() : '';
    if (normalizedType && isImageMimeType(normalizedType)) {
        return true;
    }
    const nameValue = file.name;
    const extension = getFileExtension(nameValue);
    if (!extension) {
        return false;
    }
    const guessed = resolveMimeTypeGuessFromExtension(extension);
    return Boolean(guessed && isImageMimeType(guessed));
};

const isChatAttachmentReadyForSend = (attachment: ChatAttachment | null | undefined): boolean => {
    if (!attachment) {
        return false;
    }
    if (isSoaiPathDraftRecord(attachment.soaiPathRecord)) {
        return attachment.parseStatus === 'ready';
    }
    if (!isSoaiFileAttachmentReadyForSend(attachment)) {
        return false;
    }
    return attachment.parseStatus === 'ready';
};

export { getFileExtension, isChatAttachmentReadyForSend, isSupportedChatImageFile };
