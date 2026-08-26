/* SoAI - Chat attachment creation from uploaded files [frontend/assets/ts/features/chat/attachments/attachmentCreation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';
import { isImageMimeType } from '@core/media/mimeTypes.ts';
import { isString } from '@core/typeGuards.ts';
import { isSupportedChatImageFile } from '@features/chat/ChatAttachmentSupport.ts';
import type { ChatAttachment } from '@features/chat/ChatTypes.ts';
import { normalizeImageMimeTypeFromHeader } from '@features/chat/imageMimeSniffer.ts';
import { createChatUploadFileTooLargeMessage, getChatUploadFileSizeLimit, isChatUploadFileSizeAllowed, normalizeChatUploadFileName, resolveChatUploadUnsupportedTypeLabel } from '@features/chat/attachments/attachmentValidation.ts';

interface ChatAttachmentCreationErrorHandler {
    (error: Error, title: string, options?: { notify?: boolean }): void;
}

interface ChatAttachmentCreationDependencies {
    errorHandler: ChatAttachmentCreationErrorHandler;
}

type ChatAttachmentCreationOptions = {
    forceDocument?: boolean;
};

class ChatAttachmentCreation {
    readonly #errorHandler: ChatAttachmentCreationErrorHandler;

    constructor(dependencies: ChatAttachmentCreationDependencies) {
        this.#errorHandler = dependencies.errorHandler;
    }

    async createAttachments(files: readonly File[], options: ChatAttachmentCreationOptions = {}): Promise<ChatAttachment[]> {
        const attachments: ChatAttachment[] = [];
        const sizeLimit = getChatUploadFileSizeLimit();
        const errorTitle = i18n.t('chat.upload.errorTitle');
        for (const file of files) {
            const fileName = normalizeChatUploadFileName(file);
            if (!fileName) {
                this.#errorHandler(new Error(i18n.t('chat.upload.invalidFileName')), errorTitle, { notify: true });
                continue;
            }
            if (!isChatUploadFileSizeAllowed(file, sizeLimit.maxBytes)) {
                this.#errorHandler(new Error(createChatUploadFileTooLargeMessage(fileName, sizeLimit)), errorTitle, { notify: true });
                continue;
            }
            const attachment = await this.#createAttachment(file, fileName, options, errorTitle);
            if (attachment !== null) {
                attachments.push(attachment);
            }
        }
        return attachments;
    }

    async #createAttachment(file: File, fileName: string, options: ChatAttachmentCreationOptions, errorTitle: string): Promise<ChatAttachment | null> {
        const isImage = options.forceDocument === true ? false : isSupportedChatImageFile(file);
        const effectiveFile = isImage ? await this.#resolveImageFile(file, fileName, errorTitle) : file;
        if (effectiveFile === null) {
            return null;
        }
        return {
            id: `local_${generateSecureId()}`,
            file: effectiveFile,
            name: fileName,
            size: effectiveFile.size,
            type: effectiveFile.type,
            isImage: isImage,
            parseStatus: 'processing'
        };
    }

    async #resolveImageFile(file: File, fileName: string, errorTitle: string): Promise<File | null> {
        const typeValue = file.type;
        const normalizedType = isString(typeValue) ? typeValue.trim().toLowerCase() : '';
        if (isImageMimeType(normalizedType)) {
            return file;
        }
        const normalizedFile = await normalizeImageMimeTypeFromHeader(file);
        if (normalizedFile === null) {
            const typeLabel = resolveChatUploadUnsupportedTypeLabel(file);
            const message = typeLabel ? i18n.t('chat.upload.unsupportedType', { type: typeLabel }) : i18n.t('chat.upload.unsupportedFile', { name: fileName });
            this.#errorHandler(new Error(message), errorTitle, { notify: true });
            return null;
        }
        return normalizedFile;
    }
}

export { ChatAttachmentCreation };
export type { ChatAttachmentCreationErrorHandler, ChatAttachmentCreationOptions };
