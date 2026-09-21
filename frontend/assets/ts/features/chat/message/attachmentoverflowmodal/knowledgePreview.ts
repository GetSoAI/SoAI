/* SoAI - Chat attachment overflow linked knowledge preview [frontend/assets/ts/features/chat/message/attachmentoverflowmodal/knowledgePreview.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { KnowledgeAttachmentPreviewResponse, KnowledgeAttachmentSummary } from '@core/api/contracts/webuiAttachmentContracts.ts';
import { i18n } from '@core/i18n/index.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isString } from '@core/typeGuards.ts';
import { createTextContentPreviewRequest } from '@core/ui/modals/contentpreview/requestFactories.ts';
import { requireContentPreviewModalService } from '@core/ui/modals/contentpreview/service.ts';
import type { ContentPreviewOpenRequest } from '@core/ui/modals/contentpreview/types.ts';
import { createLinkedKnowledgeClientBatchId } from '@features/chat/attachments/linkedKnowledgeClientBatchId.ts';
import { copyChatMessageTextWithFeedback, type CopyActionDependencies } from '@features/chat/message/messageCopyNotifications.ts';
import { resolveKnowledgeAttachmentPreviewText, resolveKnowledgeAttachmentPreviewTitle } from '@features/chat/message/knowledgeAttachmentPreviewPayload.ts';
import type { ChatKnowledgeAttachmentsApi } from '@features/chat/pagecontracts/types.ts';
import type { AttachmentOverflowRecord } from '@features/chat/message/attachmentoverflowmodal/records.ts';

type KnowledgePreviewDependencies = CopyActionDependencies & {
    knowledgeAttachmentsApi: Pick<ChatKnowledgeAttachmentsApi, 'previewItem' | 'useItems'>;
    isSessionActive: (sessionToken: number) => boolean;
    getAttachmentDraftRevision: () => number;
    onKnowledgeAttachmentChanged: (summary: KnowledgeAttachmentSummary) => void;
};

type KnowledgePreviewOpenArguments = {
    conversationId: string;
    knowledgeAttachmentId: string;
    record: AttachmentOverflowRecord;
    sessionToken: number;
    draftRevision: number;
};

type KnowledgePreviewOpenFromElementArguments = {
    actionElement: HTMLElement;
    conversationId: string | null;
    knowledgeAttachmentId: string | null;
    records: readonly AttachmentOverflowRecord[];
    sessionToken: number;
    draftRevision: number;
};

class AttachmentOverflowKnowledgePreview {
    readonly #knowledgeAttachmentsApi: Pick<ChatKnowledgeAttachmentsApi, 'previewItem' | 'useItems'>;
    readonly #runWithBoundary: CopyActionDependencies['runWithBoundary'];
    readonly #isSessionActive: (sessionToken: number) => boolean;
    readonly #getAttachmentDraftRevision: () => number;
    readonly #hasClipboardSupport: () => boolean;
    readonly #copyToClipboard: CopyActionDependencies['copyToClipboard'];
    readonly #showNotification: CopyActionDependencies['showNotification'];
    readonly #onKnowledgeAttachmentChanged: (summary: KnowledgeAttachmentSummary) => void;
    #controller: AbortController | null = null;
    #generation = 0;

    constructor(dependencies: KnowledgePreviewDependencies) {
        this.#knowledgeAttachmentsApi = dependencies.knowledgeAttachmentsApi;
        this.#runWithBoundary = dependencies.runWithBoundary;
        this.#isSessionActive = dependencies.isSessionActive;
        this.#getAttachmentDraftRevision = dependencies.getAttachmentDraftRevision;
        this.#hasClipboardSupport = dependencies.hasClipboardSupport;
        this.#copyToClipboard = dependencies.copyToClipboard;
        this.#showNotification = dependencies.showNotification;
        this.#onKnowledgeAttachmentChanged = dependencies.onKnowledgeAttachmentChanged;
    }

    reset(): void {
        this.#generation += 1;
        const controller = this.#controller;
        this.#controller = null;
        if (controller !== null && !controller.signal.aborted) {
            controller.abort();
        }
    }

    open(inputArguments: KnowledgePreviewOpenArguments): void {
        const itemId = inputArguments.record.knowledgeItemId;
        if (itemId === null) {
            throw new Error('Linked knowledge preview requires an item id');
        }
        this.reset();
        this.#generation += 1;
        const generation = this.#generation;
        const controller = new AbortController();
        this.#controller = controller;
        terminateHandledPromise(this.#runWithBoundary('chat:attachmentOverflowKnowledgePreviewOpen', () => this.#runOpen(inputArguments, itemId, generation, controller.signal)));
    }

    openFromActionElement(inputArguments: KnowledgePreviewOpenFromElementArguments): void {
        if (inputArguments.conversationId === null || inputArguments.knowledgeAttachmentId === null) {
            return;
        }
        const record = this.#findRecordByElement(inputArguments.actionElement, inputArguments.records);
        if (record === null) {
            return;
        }
        this.open({
            conversationId: inputArguments.conversationId,
            knowledgeAttachmentId: inputArguments.knowledgeAttachmentId,
            record,
            sessionToken: inputArguments.sessionToken,
            draftRevision: inputArguments.draftRevision
        });
    }

    async #runOpen(inputArguments: KnowledgePreviewOpenArguments, itemId: number, generation: number, signal: AbortSignal): Promise<void> {
        try {
            const payload = await this.#runWithBoundary('chat:attachmentOverflowKnowledgeItemPreview', () => this.#knowledgeAttachmentsApi.previewItem(inputArguments.conversationId, inputArguments.knowledgeAttachmentId, String(itemId), { documentId: inputArguments.record.documentId }, { signal }));
            if (!this.#isCurrent(inputArguments.sessionToken, generation, signal, inputArguments.draftRevision)) {
                return;
            }
            requireContentPreviewModalService().open(this.#buildRequest(inputArguments, itemId, payload, generation, signal));
        } catch (error) {
            if (isAbortError(error)) {
                return;
            }
            throw ensureError(error);
        }
    }

    #buildRequest(inputArguments: KnowledgePreviewOpenArguments, itemId: number, payload: KnowledgeAttachmentPreviewResponse, generation: number, signal: AbortSignal): ContentPreviewOpenRequest {
        return createTextContentPreviewRequest({
            scope: 'chat',
            type: 'text',
            headerDescription: i18n.t('chat.attachments.badge.knowledge'),
            baseline: {
                title: resolveKnowledgeAttachmentPreviewTitle(payload, inputArguments.record.title),
                content: resolveKnowledgeAttachmentPreviewText(payload),
                promptColor: null
            },
            editable: false,
            languageMode: 'default',
            disableCopyWhenEmpty: true,
            disableDownloadWhenEmpty: true,
            colorToolkit: null,
            sourceReference: null,
            onRequestSave: null,
            onRequestDownload: null,
            onRequestCopy: async (text) => await this.#copyText(text),
            onRequestAttach: () => this.#attachItem(inputArguments, itemId, generation, signal),
            enhance: null,
            openSourceUrl: null,
            externalOpenBehavior: 'neverConfirm',
            onStatePotentiallyChanged: null
        });
    }

    async #copyText(text: string): Promise<void> {
        await copyChatMessageTextWithFeedback(
            {
                copyToClipboard: (value, options) => this.#copyToClipboard(value, options),
                hasClipboardSupport: () => this.#hasClipboardSupport(),
                showNotification: (message, type) => this.#showNotification(message, type)
            },
            text
        );
    }

    async #attachItem(inputArguments: KnowledgePreviewOpenArguments, itemId: number, generation: number, signal: AbortSignal): Promise<void> {
        if (!this.#isCurrent(inputArguments.sessionToken, generation, signal, inputArguments.draftRevision)) {
            return;
        }
        const response = await this.#runWithBoundary('chat:attachmentOverflowKnowledgeAttach', () =>
            this.#knowledgeAttachmentsApi.useItems(
                inputArguments.conversationId,
                {
                    sourceConvId: inputArguments.conversationId,
                    sourceKnowledgeAttachmentId: inputArguments.knowledgeAttachmentId,
                    selections: [
                        {
                            itemId: itemId,
                            documentId: inputArguments.record.documentId
                        }
                    ],
                    clientBatchId: createLinkedKnowledgeClientBatchId({
                        targetConversationId: inputArguments.conversationId,
                        sourceConversationId: inputArguments.conversationId,
                        sourceKnowledgeAttachmentId: inputArguments.knowledgeAttachmentId,
                        selections: [
                            {
                                itemId: itemId,
                                documentId: inputArguments.record.documentId
                            }
                        ]
                    })
                },
                { signal }
            )
        );
        if (this.#isCurrent(inputArguments.sessionToken, generation, signal, inputArguments.draftRevision)) {
            this.#onKnowledgeAttachmentChanged(response.summary);
            requireContentPreviewModalService().close();
        }
    }

    #isCurrent(sessionToken: number, generation: number, signal: AbortSignal, draftRevision: number): boolean {
        return !signal.aborted && this.#generation === generation && this.#isSessionActive(sessionToken) && this.#getAttachmentDraftRevision() === draftRevision;
    }

    #findRecordByElement(actionElement: HTMLElement, records: readonly AttachmentOverflowRecord[]): AttachmentOverflowRecord | null {
        const collectionId = actionElement.dataset['collectionId'];
        if (!isString(collectionId) || !collectionId.trim()) {
            return null;
        }
        const record = records.find((item) => item.id === collectionId.trim());
        return record ?? null;
    }
}

export { AttachmentOverflowKnowledgePreview };
