/* SoAI - Chat attachment asynchronous processing queue [frontend/assets/ts/features/chat/attachments/attachmentProcessingQueue.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ModuleLogger } from '@core/moduleContext.ts';
import { isString } from '@core/typeGuards.ts';
import type { ChatAttachment } from '@features/chat/ChatTypes.ts';
import { readChatImagePreviewDataUrl } from '@features/chat/attachments/attachmentImagePreviewReader.ts';
import type { PhysicalAttachmentPayload } from '@core/realtime/eventcontracts/attachmentContracts.ts';

interface ChatAttachmentProcessorContract {
    abortAttachment(attachmentId: string): void;
    waitForAttachments(files: readonly ChatAttachment[]): Promise<void>;
    waitForAttachment(attachment: ChatAttachment): Promise<void>;
    processAttachment(attachment: ChatAttachment): Promise<PhysicalAttachmentPayload | null>;
}

interface ChatAttachmentProcessingErrorHandler {
    (error: Error, title: string, options?: { notify?: boolean }): void;
}

interface ChatAttachmentProcessingQueueDependencies {
    attachmentProcessor: ChatAttachmentProcessorContract;
    logger: ModuleLogger;
    errorHandler: ChatAttachmentProcessingErrorHandler;
    onAttachmentChanged: () => void;
}

class ChatAttachmentProcessingQueue {
    readonly #attachmentProcessor: ChatAttachmentProcessorContract;
    readonly #logger: ModuleLogger;
    readonly #errorHandler: ChatAttachmentProcessingErrorHandler;
    readonly #onAttachmentChanged: () => void;
    readonly #imageReads: Map<string, Promise<void>>;
    readonly #activeAttachmentIds: Set<string>;
    readonly #removedAttachmentIds: Set<string>;

    constructor(dependencies: ChatAttachmentProcessingQueueDependencies) {
        this.#attachmentProcessor = dependencies.attachmentProcessor;
        this.#logger = dependencies.logger;
        this.#errorHandler = dependencies.errorHandler;
        this.#onAttachmentChanged = dependencies.onAttachmentChanged;
        this.#imageReads = new Map();
        this.#activeAttachmentIds = new Set();
        this.#removedAttachmentIds = new Set();
    }

    clear(): void {
        for (const attachmentId of this.#activeAttachmentIds) {
            this.#attachmentProcessor.abortAttachment(attachmentId);
            this.#removedAttachmentIds.add(attachmentId);
        }
        for (const attachmentId of this.#imageReads.keys()) {
            this.#removedAttachmentIds.add(attachmentId);
        }
        this.#imageReads.clear();
    }

    deleteAttachment(attachmentId: string): void {
        this.#attachmentProcessor.abortAttachment(attachmentId);
        this.#removedAttachmentIds.add(attachmentId);
        this.#imageReads.delete(attachmentId);
    }

    async waitForAttachments(attachments: readonly ChatAttachment[]): Promise<void> {
        if (attachments.length === 0) {
            return;
        }
        const imagePromises: Promise<void>[] = [];
        for (const attachment of attachments) {
            if (!attachment || !attachment.isImage) {
                continue;
            }
            const readPromise = this.#imageReads.get(attachment.id);
            if (readPromise) {
                imagePromises.push(readPromise);
            }
        }
        await Promise.allSettled([this.#attachmentProcessor.waitForAttachments(attachments), ...imagePromises]);
    }

    async waitForAttachment(attachment: ChatAttachment): Promise<void> {
        const imagePromise = this.#imageReads.get(attachment.id);
        const waits = imagePromise ? [this.#attachmentProcessor.waitForAttachment(attachment), imagePromise] : [this.#attachmentProcessor.waitForAttachment(attachment)];
        await Promise.allSettled(waits);
    }

    processAttachment(attachment: ChatAttachment): Promise<void> {
        this.#activeAttachmentIds.add(attachment.id);
        this.#removedAttachmentIds.delete(attachment.id);
        if (attachment.isImage) {
            return this.#processImageAttachment(attachment);
        }
        return this.#processDocumentAttachment(attachment);
    }

    async #processDocumentAttachment(attachment: ChatAttachment): Promise<void> {
        try {
            await this.#processPhysicalAttachment(attachment);
        } finally {
            this.#removedAttachmentIds.delete(attachment.id);
        }
    }

    async #processImageAttachment(attachment: ChatAttachment): Promise<void> {
        const errorTitle = i18n.t('chat.upload.errorTitle');
        const file = attachment.file;
        if (!file) {
            attachment.parseStatus = 'error';
            attachment.parseError = i18n.t('chat.upload.imageReadFailed');
            this.#activeAttachmentIds.delete(attachment.id);
            this.#onAttachmentChanged();
            return;
        }
        const previewOperation = readChatImagePreviewDataUrl(file, this.#logger)
            .then((dataUrl) => {
                if (!this.#removedAttachmentIds.has(attachment.id) && (!isString(attachment.previewUrl) || !attachment.previewUrl.trim())) {
                    attachment.previewUrl = dataUrl;
                }
            })
            .catch((error) => {
                if (this.#removedAttachmentIds.has(attachment.id)) {
                    return;
                }
                const runtimeError = ensureError(error);
                const message = i18n.t('chat.upload.imageReadFailed');
                attachment.parseError = message;
                this.#errorHandler(runtimeError, errorTitle, { notify: true });
            })
            .finally(() => {
                this.#imageReads.delete(attachment.id);
                this.#onAttachmentChanged();
            });
        this.#imageReads.set(attachment.id, previewOperation);
        try {
            await Promise.allSettled([previewOperation, this.#processPhysicalAttachment(attachment)]);
        } finally {
            this.#removedAttachmentIds.delete(attachment.id);
        }
    }

    async #processPhysicalAttachment(attachment: ChatAttachment): Promise<void> {
        const errorTitle = i18n.t('chat.upload.errorTitle');
        try {
            await this.#attachmentProcessor.processAttachment(attachment);
        } catch (error) {
            if (this.#removedAttachmentIds.has(attachment.id) && isAbortError(ensureError(error))) {
                return;
            }
            attachment.parseStatus = 'error';
            const processingError = ensureError(error);
            if (!isString(attachment.parseError) || !attachment.parseError.trim()) {
                attachment.parseError = processingError.message;
            }
            this.#logger('error', 'Document processing failed', processingError);
            const message = i18n.t('chat.attachments.parseErrorNotification', {
                name: attachment.name,
                error: attachment.parseError
            });
            this.#errorHandler(new Error(message), errorTitle, { notify: true });
        } finally {
            this.#activeAttachmentIds.delete(attachment.id);
        }
    }
}

export { ChatAttachmentProcessingQueue };
export type { ChatAttachmentProcessorContract, ChatAttachmentProcessingErrorHandler };
