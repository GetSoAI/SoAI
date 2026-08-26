/* SoAI - Chat SoAI path image preview object URL lifecycle [frontend/assets/ts/features/chat/attachments/soaiPathImagePreviewLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import type { ModuleLogger } from '@core/moduleContext.ts';
import type { ChatAttachment } from '@features/chat/ChatTypes.ts';
import { isSoaiPathDraftRecord, type SoaiPathDraftRecord } from '@features/chat/attachments/soaiPathDraftRecords.ts';

type SoaiPathImagePreviewLoader = (record: SoaiPathDraftRecord, signal: AbortSignal) => Promise<string | null>;

type SoaiPathImagePreviewLifecycleOptions = {
    logger: ModuleLogger;
    loadPreview: SoaiPathImagePreviewLoader | null;
};

class SoaiPathImagePreviewLifecycle {
    readonly #logger: ModuleLogger;
    readonly #loadPreview: SoaiPathImagePreviewLoader | null;
    readonly #controllers = new Map<string, AbortController>();
    readonly #objectUrls = new Map<string, string>();
    readonly #attachments = new Map<string, ChatAttachment>();
    readonly #operations = new Set<Promise<void>>();

    constructor(options: SoaiPathImagePreviewLifecycleOptions) {
        this.#logger = options.logger;
        this.#loadPreview = options.loadPreview;
    }

    load(attachment: ChatAttachment, isCurrent: (attachmentId: string) => boolean, syncUi: () => void): void {
        const record = attachment.soaiPathRecord;
        if (!attachment.isImage || !isSoaiPathDraftRecord(record) || this.#loadPreview === null) {
            return;
        }
        this.release(attachment);
        const controller = new AbortController();
        this.#controllers.set(attachment.id, controller);
        const operation = this.#runLoad(attachment, record, controller, isCurrent, syncUi);
        this.#operations.add(operation);
        void operation.then(
            () => {
                this.#operations.delete(operation);
            },
            () => {
                this.#operations.delete(operation);
            }
        );
    }

    #clearObjectUrl(attachmentId: string, fallbackAttachment: ChatAttachment | null): void {
        const objectUrl = this.#objectUrls.get(attachmentId);
        const attachment = this.#attachments.get(attachmentId) ?? fallbackAttachment;
        this.#objectUrls.delete(attachmentId);
        this.#attachments.delete(attachmentId);
        if (objectUrl !== undefined) {
            URL.revokeObjectURL(objectUrl);
        }
        if (attachment !== null && attachment.previewUrl === objectUrl) {
            delete attachment.previewUrl;
        }
    }

    release(attachment: ChatAttachment): void {
        const controller = this.#controllers.get(attachment.id);
        this.#controllers.delete(attachment.id);
        if (controller !== undefined && !controller.signal.aborted) {
            controller.abort();
        }
        this.#clearObjectUrl(attachment.id, attachment);
    }

    releaseAll(attachments: readonly ChatAttachment[]): void {
        for (const attachment of attachments) {
            this.release(attachment);
        }
    }

    dispose(): void {
        for (const controller of this.#controllers.values()) {
            if (!controller.signal.aborted) {
                controller.abort();
            }
        }
        this.#controllers.clear();
        for (const attachmentId of this.#objectUrls.keys()) {
            this.#clearObjectUrl(attachmentId, null);
        }
        this.#attachments.clear();
    }

    async #runLoad(attachment: ChatAttachment, record: SoaiPathDraftRecord, controller: AbortController, isCurrent: (attachmentId: string) => boolean, syncUi: () => void): Promise<void> {
        try {
            const objectUrl = await this.#loadPreview?.(record, controller.signal);
            if (objectUrl === null || objectUrl === undefined) {
                return;
            }
            if (controller.signal.aborted || !isCurrent(attachment.id)) {
                URL.revokeObjectURL(objectUrl);
                return;
            }
            this.#objectUrls.set(attachment.id, objectUrl);
            this.#attachments.set(attachment.id, attachment);
            attachment.previewUrl = objectUrl;
            syncUi();
        } catch (error) {
            if (!controller.signal.aborted) {
                this.#logger('warn', 'Failed to load SoAI path image preview', ensureError(error));
            }
        } finally {
            if (this.#controllers.get(attachment.id) === controller) {
                this.#controllers.delete(attachment.id);
            }
        }
    }
}

export { SoaiPathImagePreviewLifecycle };
export type { SoaiPathImagePreviewLoader };
