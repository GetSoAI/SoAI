/* SoAI - Chat attachment overflow linked knowledge first preview [frontend/assets/ts/features/chat/message/attachmentoverflowmodal/knowledgeFirstPreview.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isString } from '@core/typeGuards.ts';
import type { KnowledgeAttachmentSummary } from '@core/api/contracts/webuiAttachmentContracts.ts';
import { openKnowledgeAttachmentFirstPreview } from '@features/chat/message/knowledgeAttachmentFirstPreview.ts';
import type { CopyActionDependencies } from '@features/chat/message/messageCopyNotifications.ts';
import type { ChatKnowledgeAttachmentsApi } from '@features/chat/pagecontracts/types.ts';

type KnowledgeFirstPreviewDependencies = CopyActionDependencies & {
    knowledgeAttachmentsApi: Pick<ChatKnowledgeAttachmentsApi, 'items' | 'previewItem' | 'useItems'>;
    isSessionActive: (sessionToken: number) => boolean;
    onKnowledgeAttachmentChanged: (summary: KnowledgeAttachmentSummary) => void;
};

type KnowledgeFirstPreviewOpenArguments = {
    actionElement: HTMLElement;
    conversationId: string | null;
    sessionToken: number;
};

type KnowledgeFirstPreviewRunArguments = {
    controller: AbortController;
    conversationId: string;
    knowledgeAttachmentId: string;
    title: string;
    sessionToken: number;
};

class AttachmentOverflowKnowledgeFirstPreview {
    readonly #knowledgeAttachmentsApi: Pick<ChatKnowledgeAttachmentsApi, 'items' | 'previewItem' | 'useItems'>;
    readonly #runWithBoundary: CopyActionDependencies['runWithBoundary'];
    readonly #isSessionActive: (sessionToken: number) => boolean;
    readonly #hasClipboardSupport: () => boolean;
    readonly #copyToClipboard: CopyActionDependencies['copyToClipboard'];
    readonly #showNotification: CopyActionDependencies['showNotification'];
    readonly #onKnowledgeAttachmentChanged: (summary: KnowledgeAttachmentSummary) => void;
    #controller: AbortController | null = null;

    constructor(dependencies: KnowledgeFirstPreviewDependencies) {
        this.#knowledgeAttachmentsApi = dependencies.knowledgeAttachmentsApi;
        this.#runWithBoundary = dependencies.runWithBoundary;
        this.#isSessionActive = dependencies.isSessionActive;
        this.#hasClipboardSupport = dependencies.hasClipboardSupport;
        this.#copyToClipboard = dependencies.copyToClipboard;
        this.#showNotification = dependencies.showNotification;
        this.#onKnowledgeAttachmentChanged = dependencies.onKnowledgeAttachmentChanged;
    }

    reset(): void {
        const controller = this.#controller;
        this.#controller = null;
        if (controller !== null && !controller.signal.aborted) {
            controller.abort();
        }
    }

    openFromActionElement(inputArguments: KnowledgeFirstPreviewOpenArguments): void {
        const conversationId = inputArguments.conversationId;
        const knowledgeAttachmentId = inputArguments.actionElement.dataset['knowledgeAttachmentId'];
        if (!isString(conversationId) || !conversationId.trim() || !isString(knowledgeAttachmentId) || !knowledgeAttachmentId.trim()) {
            return;
        }
        this.reset();
        const controller = new AbortController();
        this.#controller = controller;
        const title = inputArguments.actionElement.getAttribute('aria-label') ?? inputArguments.actionElement.textContent ?? '';
        terminateHandledPromise(
            this.#runWithBoundary(
                'chat:attachmentOverflowKnowledgeFirstPreview',
                async () =>
                    await this.#runOpen({
                        controller,
                        conversationId: conversationId.trim(),
                        knowledgeAttachmentId: knowledgeAttachmentId.trim(),
                        title: title.trim(),
                        sessionToken: inputArguments.sessionToken
                    })
            )
        );
    }

    async #runOpen(inputArguments: KnowledgeFirstPreviewRunArguments): Promise<void> {
        try {
            await openKnowledgeAttachmentFirstPreview({
                knowledgeAttachmentsApi: this.#knowledgeAttachmentsApi,
                targetConversationId: inputArguments.conversationId,
                sourceConversationId: inputArguments.conversationId,
                knowledgeAttachmentId: inputArguments.knowledgeAttachmentId,
                fallbackTitle: inputArguments.title,
                hasClipboardSupport: () => this.#hasClipboardSupport(),
                copyToClipboard: (text, options) => this.#copyToClipboard(text, options),
                showNotification: (message, type) => this.#showNotification(message, type),
                onKnowledgeAttachmentChanged: (summary) => this.#onKnowledgeAttachmentChanged(summary),
                shouldOpen: () => this.#isSessionActive(inputArguments.sessionToken),
                shouldAttach: () => this.#isSessionActive(inputArguments.sessionToken),
                signal: inputArguments.controller.signal
            });
        } catch (error) {
            if (isAbortError(error)) {
                return;
            }
            throw ensureError(error);
        } finally {
            if (this.#controller === inputArguments.controller) {
                this.#controller = null;
            }
        }
    }
}

export { AttachmentOverflowKnowledgeFirstPreview };
