/* SoAI - Chat feature attachment processor [frontend/assets/ts/features/chat/ChatAttachmentProcessor.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { coerceErrorMessage } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';
import { isArray, isFunction, isString } from '@core/typeGuards.ts';
import type { ChatAttachment } from '@features/chat/ChatTypes.ts';
import type { PhysicalAttachmentPayload } from '@core/realtime/eventcontracts/attachmentContracts.ts';
import { applyPhysicalAttachmentPayloadToChatAttachment, mapPhysicalAttachmentResponse } from '@features/chat/attachments/physicalAttachmentPayload.ts';
import type { ChatPageApi } from '@features/chat/pagecontracts/types.ts';

interface ChatParent {
    api: ChatPageApi;
    resolveConversationId: () => Promise<string>;
    runWithBoundary: <T>(scope: string, handler: () => Promise<T>) => Promise<T>;
    uiManager?: {
        updateAttachmentsPreview(): void;
        updateInputState(): void;
    };
}

const ATTACHMENT_UPLOAD_SOURCE = 'composer';

const resolveClientAttachmentId = (attachment: ChatAttachment): string => {
    if (isString(attachment.clientAttachmentId) && attachment.clientAttachmentId.trim()) {
        return attachment.clientAttachmentId.trim();
    }
    const clientAttachmentId = attachment.id.trim();
    attachment.clientAttachmentId = clientAttachmentId;
    return clientAttachmentId;
};

const resolveClientRequestId = (attachment: ChatAttachment): string => {
    if (isString(attachment.clientRequestId) && attachment.clientRequestId.trim()) {
        return attachment.clientRequestId.trim();
    }
    const clientRequestId = generateSecureId({ prefix: 'chat_attachment_req', separator: '_' });
    attachment.clientRequestId = clientRequestId;
    return clientRequestId;
};

class ChatAttachmentProcessor {
    readonly #parent: ChatParent;
    readonly #processing: Map<string, Promise<PhysicalAttachmentPayload | null>>;
    readonly #abortControllers: Map<string, AbortController>;

    constructor(parent: ChatParent) {
        if (!parent) {
            throw new Error('ChatAttachmentProcessor requires a chat page host');
        }
        if (!isFunction(parent.resolveConversationId)) {
            throw new Error('ChatAttachmentProcessor requires resolveConversationId');
        }
        if (!isFunction(parent.runWithBoundary)) {
            throw new Error('ChatAttachmentProcessor requires runWithBoundary');
        }
        this.#parent = parent;
        this.#processing = new Map();
        this.#abortControllers = new Map();
    }

    async processAttachment(attachment: ChatAttachment): Promise<PhysicalAttachmentPayload | null> {
        const file = attachment.file;
        if (!attachment || !file) {
            return null;
        }
        if (this.#processing.has(attachment.id)) {
            const existing = this.#processing.get(attachment.id);
            if (existing) {
                return existing;
            }
        }
        attachment.parseStatus = 'processing';
        attachment.parseError = '';
        const abortController = new AbortController();
        this.#abortControllers.set(attachment.id, abortController);

        const finalizeTask = async (): Promise<PhysicalAttachmentPayload | null> => {
            try {
                return await this.#stageAttachment(attachment, file, abortController.signal);
            } catch (error) {
                attachment.parseStatus = 'error';
                attachment.parseError = coerceErrorMessage(error, i18n.t('documents.errors.parseFailed'));
                throw error;
            } finally {
                this.#processing.delete(attachment.id);
                this.#abortControllers.delete(attachment.id);
                this.#parent.uiManager?.updateAttachmentsPreview();
                this.#parent.uiManager?.updateInputState();
            }
        };

        const task = finalizeTask();
        this.#processing.set(attachment.id, task);
        return task;
    }

    abortAttachment(attachmentId: string): void {
        const controller = this.#abortControllers.get(attachmentId);
        if (controller !== undefined) {
            controller.abort();
        }
    }

    async #stageAttachment(attachment: ChatAttachment, file: File, signal: AbortSignal): Promise<PhysicalAttachmentPayload> {
        const conversationId = await this.#parent.resolveConversationId();
        const clientAttachmentId = resolveClientAttachmentId(attachment);
        const clientRequestId = resolveClientRequestId(attachment);
        const response = await this.#parent.runWithBoundary('chat:attachmentStageUpload', () =>
            this.#parent.api.webui.chat.attachments.stage(
                conversationId,
                {
                    file,
                    displayName: attachment.name,
                    source: ATTACHMENT_UPLOAD_SOURCE,
                    clientAttachmentId,
                    clientRequestId
                },
                { signal }
            )
        );
        const payload = mapPhysicalAttachmentResponse(response);
        applyPhysicalAttachmentPayloadToChatAttachment(attachment, conversationId, payload);
        return payload;
    }

    async waitForAttachment(attachment: ChatAttachment): Promise<void> {
        if (!attachment) {
            return;
        }
        const promise = this.#processing.get(attachment.id);
        if (promise) {
            await promise;
        }
    }

    async waitForAttachments(list: readonly ChatAttachment[]): Promise<void> {
        if (!isArray(list) || list.length === 0) {
            return;
        }
        const attachmentPromises: Promise<void>[] = [];
        for (const item of list) {
            if (item) {
                attachmentPromises.push(this.waitForAttachment(item));
            }
        }
        await Promise.allSettled(attachmentPromises);
    }
}

export { ChatAttachmentProcessor };
export type { PhysicalAttachmentPayload };
