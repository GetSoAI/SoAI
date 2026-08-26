/* SoAI - Chat attach modal draft attachment list controller [frontend/assets/ts/pages/chat/controllers/modals/chatattach/ChatAttachDraftAttachmentListController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatAttachment } from '@features/chat/public.ts';
import type { ChatAttachDraftListHost } from '@pages/chat/controllers/modals/chatattach/contracts.ts';
import { renderDraftAttachmentListState } from '@pages/chat/controllers/modals/chatattach/chatAttachDraftAttachmentListStateWidget.ts';
import type { ChatAttachDraftAttachmentListElements, ChatAttachDraftAttachmentListEntry } from '@pages/chat/controllers/modals/chatattach/types.ts';

class ChatAttachDraftAttachmentListController {
    readonly #host: ChatAttachDraftListHost;
    readonly #elements: ChatAttachDraftAttachmentListElements;
    readonly #signal: AbortSignal;
    #unsubscribeDrafts: (() => void) | null = null;

    constructor(host: ChatAttachDraftListHost, elements: ChatAttachDraftAttachmentListElements, signal: AbortSignal) {
        this.#host = host;
        this.#elements = elements;
        this.#signal = signal;
        this.#bind();
        this.#render();
    }

    activate(): void {
        if (this.#unsubscribeDrafts !== null) {
            return;
        }
        this.#unsubscribeDrafts = this.#host.attachments.subscribeDrafts(() => this.#render());
        this.#render();
    }

    deactivate(): void {
        this.#unsubscribeDrafts?.();
        this.#unsubscribeDrafts = null;
    }

    #bind(): void {
        this.#elements.list.addEventListener(
            'click',
            (event: Event): void => {
                const target = event.target;
                if (!(target instanceof Element)) {
                    return;
                }
                const deleteButton = target.closest('.chat-attach-draft-attachment-row-delete');
                if (!(deleteButton instanceof HTMLButtonElement)) {
                    return;
                }
                const fileId = deleteButton.dataset['fileId'] ?? null;
                if (fileId === null || !fileId.trim()) {
                    return;
                }
                this.#host.execution.run('chat:attachModalDraftAttachmentRemove', async () => {
                    await this.#host.attachments.removeFile(fileId);
                });
            },
            { signal: this.#signal }
        );
    }

    #render(): void {
        const entries = this.#host.attachments.drafts().map((attachment) => this.#toEntry(attachment));
        const processingCount = entries.filter((entry) => entry.attachment.parseStatus === 'processing').length;
        const readyCount = entries.filter((entry) => entry.attachment.parseStatus === 'ready').length;
        renderDraftAttachmentListState(this.#elements, entries, processingCount, readyCount);
    }

    #toEntry(attachment: ChatAttachment): ChatAttachDraftAttachmentListEntry {
        return { attachment };
    }
}

export { ChatAttachDraftAttachmentListController };
