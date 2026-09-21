/* SoAI - Chat attach modal draft attachment list controller [frontend/assets/ts/pages/chat/controllers/modals/chatattach/ChatAttachDraftAttachmentListController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveChatAttachmentDraftSource, resolveDraftAttachmentIconName, resolvePhysicalAttachmentPreviewUrl, type ChatAttachment, type ChatAttachmentDraftSource } from '@features/chat/public.ts';
import { securityApi } from '@core/security/public.ts';
import type { ChatAttachDraftListHost } from '@pages/chat/controllers/modals/chatattach/contracts.ts';
import { renderDraftAttachmentListState } from '@pages/chat/controllers/modals/chatattach/chatAttachDraftAttachmentListStateWidget.ts';
import type { ChatAttachDraftAttachmentListElements, ChatAttachDraftAttachmentListEntry } from '@pages/chat/controllers/modals/chatattach/types.ts';

const resolveChatAttachDraftListAttachments = (attachments: readonly ChatAttachment[], source: ChatAttachmentDraftSource): ChatAttachment[] => attachments.filter((attachment) => resolveChatAttachmentDraftSource(attachment) === source).reverse();

class ChatAttachDraftAttachmentListController {
    readonly #host: ChatAttachDraftListHost;
    readonly #elements: ChatAttachDraftAttachmentListElements;
    readonly #signal: AbortSignal;
    readonly #source: ChatAttachmentDraftSource;
    #unsubscribeDrafts: (() => void) | null = null;

    constructor(host: ChatAttachDraftListHost, elements: ChatAttachDraftAttachmentListElements, signal: AbortSignal, source: ChatAttachmentDraftSource) {
        this.#host = host;
        this.#elements = elements;
        this.#signal = signal;
        this.#source = source;
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
        const conversationId = this.#host.conversation.currentId();
        const entries: ChatAttachDraftAttachmentListEntry[] = [];
        let processingCount = 0;
        let readyCount = 0;
        for (const attachment of resolveChatAttachDraftListAttachments(this.#host.attachments.drafts(), this.#source)) {
            entries.push(this.#toEntry(attachment, conversationId));
            if (attachment.parseStatus === 'processing') {
                processingCount += 1;
            } else if (attachment.parseStatus === 'ready') {
                readyCount += 1;
            }
        }
        renderDraftAttachmentListState(this.#elements, entries, processingCount, readyCount);
    }

    #toEntry(attachment: ChatAttachment, conversationId: string | null): ChatAttachDraftAttachmentListEntry {
        const iconName = resolveDraftAttachmentIconName(attachment);
        const previewCandidate = resolvePhysicalAttachmentPreviewUrl(conversationId, attachment);
        const previewUrl = previewCandidate === null ? null : securityApi.sanitizeImageSource(previewCandidate);
        return { attachment, iconName, previewUrl };
    }
}

export { ChatAttachDraftAttachmentListController, resolveChatAttachDraftListAttachments };
