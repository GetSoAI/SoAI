/* SoAI - Shared file validation helpers for chat attachments [frontend/assets/ts/features/chat/attachments/attachmentValidation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getMaxFileUploadBytes } from '@core/api/systemLimitsService.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatBytes } from '@core/primitives/byteSize.ts';
import { isString } from '@core/typeGuards.ts';
import { getFileExtension } from '@features/chat/ChatAttachmentSupport.ts';

interface ChatUploadFileSizeLimit {
    maxBytes: number;
    maxSizeLabel: string;
}

const normalizeChatUploadFileName = (file: File): string | null => {
    const fileName = file.name;
    if (!isString(fileName)) {
        return null;
    }
    const trimmed = fileName.trim();
    return trimmed ? trimmed : null;
};

const isChatUploadFileSizeAllowed = (file: File, maxBytes: number): boolean => {
    if (!Number.isFinite(maxBytes) || maxBytes <= 0) {
        throw new Error('Chat attachment validation requires a valid max file size.');
    }
    return file.size <= maxBytes;
};

const getChatUploadFileSizeLimit = (): ChatUploadFileSizeLimit => {
    const maxBytes = getMaxFileUploadBytes();
    return {
        maxBytes,
        maxSizeLabel: formatBytes(maxBytes)
    };
};

const createChatUploadFileTooLargeMessage = (fileName: string, limit: ChatUploadFileSizeLimit): string => {
    return i18n.t('chat.upload.fileTooLarge', { name: fileName, maxSize: limit.maxSizeLabel });
};

const resolveChatUploadUnsupportedTypeLabel = (file: File): string | null => {
    const rawType = file.type;
    if (isString(rawType)) {
        const trimmedType = rawType.trim();
        if (trimmedType) {
            return trimmedType;
        }
    }
    const extension = getFileExtension(file.name);
    if (extension) {
        return `.${extension}`;
    }
    return null;
};

export { createChatUploadFileTooLargeMessage, getChatUploadFileSizeLimit, isChatUploadFileSizeAllowed, normalizeChatUploadFileName, resolveChatUploadUnsupportedTypeLabel };
export type { ChatUploadFileSizeLimit };
