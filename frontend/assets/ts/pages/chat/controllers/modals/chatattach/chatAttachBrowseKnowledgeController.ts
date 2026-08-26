/* SoAI - Chat attach modal reusable knowledge operations [frontend/assets/ts/pages/chat/controllers/modals/chatattach/chatAttachBrowseKnowledgeController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { KnowledgeAttachmentItemsResponse } from '@core/api/contracts/webuiAttachmentContracts.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedStringOrNull } from '@core/normalize.ts';
import { copyTextWithHostClipboardFeedback } from '@core/ui/notifications/clipboardCopy.ts';
import { createTextContentPreviewRequest } from '@core/ui/modals/contentpreview/requestFactories.ts';
import { requireContentPreviewModalService } from '@core/ui/modals/contentpreview/service.ts';
import { showUserError } from '@core/ui/notifications/notifications.ts';
import { createLinkedKnowledgeClientBatchId, resolveKnowledgeAttachmentPreviewText, resolveKnowledgeAttachmentPreviewTitle } from '@features/chat/public.ts';
import type { ChatAttachBrowseKnowledgeHost } from '@pages/chat/controllers/modals/chatattach/contracts.ts';
import { abortTrackedBrowseAbortControllers, createTrackedBrowseAbortController, releaseTrackedBrowseAbortController, type BrowseAbortControllerRegistry } from '@pages/chat/controllers/modals/chatattach/chatAttachBrowseAbortController.ts';
import type { ChatAttachBrowseResult } from '@pages/chat/controllers/modals/chatattach/chatAttachBrowseResultsWidget.ts';

type KnowledgeBrowseResult = Extract<ChatAttachBrowseResult, { type: 'knowledge' }>;
type BrowseActionGuard = () => boolean;

type KnowledgeSelection = {
    itemId: number;
    documentId: string | null;
};

const parseKnowledgeSelections = (payload: KnowledgeAttachmentItemsResponse): KnowledgeSelection[] => payload.items.map((item) => ({ itemId: item.id, documentId: item.documentId }));

class ChatAttachBrowseKnowledgeOperations {
    readonly #host: ChatAttachBrowseKnowledgeHost;
    readonly #signal: AbortSignal;
    readonly #controllers: BrowseAbortControllerRegistry = new Set();

    constructor(host: ChatAttachBrowseKnowledgeHost, signal: AbortSignal) {
        this.#host = host;
        this.#signal = signal;
    }

    async preview(result: KnowledgeBrowseResult, isCurrent: BrowseActionGuard): Promise<void> {
        if (!isCurrent()) {
            return;
        }
        const controller = createTrackedBrowseAbortController(this.#controllers, this.#signal);
        try {
            const selection = await this.#firstSelection(result, controller.signal);
            if (controller.signal.aborted || !isCurrent()) {
                return;
            }
            const payload = await this.#host.shared.api.webui.chat.attachments.knowledge.previewItem(result.sourceConversationId, result.knowledgeAttachmentId, String(selection.itemId), { documentId: selection.documentId }, { signal: controller.signal });
            if (controller.signal.aborted || !isCurrent()) {
                return;
            }
            requireContentPreviewModalService().open(
                createTextContentPreviewRequest({
                    scope: 'chat',
                    type: 'text',
                    headerDescription: i18n.t('chat.attachModal.browseChipKnowledge'),
                    baseline: { title: resolveKnowledgeAttachmentPreviewTitle(payload, result.title), content: resolveKnowledgeAttachmentPreviewText(payload), promptColor: null },
                    editable: false,
                    languageMode: 'default',
                    disableCopyWhenEmpty: true,
                    disableDownloadWhenEmpty: true,
                    colorToolkit: null,
                    onRequestSave: null,
                    onRequestDownload: null,
                    onRequestCopy: async (text) => await this.#copyPreviewText(text),
                    onRequestAttach: async () => {
                        await this.attach(result, isCurrent);
                    },
                    enhance: null,
                    openSourceUrl: null,
                    onStatePotentiallyChanged: null,
                    sourceReference: null,
                    externalOpenBehavior: 'neverConfirm'
                })
            );
        } catch (error) {
            if (controller.signal.aborted) {
                return;
            }
            throw ensureError(error);
        } finally {
            releaseTrackedBrowseAbortController(this.#controllers, controller);
        }
    }

    async attach(result: KnowledgeBrowseResult, isCurrent: BrowseActionGuard): Promise<boolean> {
        const targetConversationId = toTrimmedStringOrNull(this.#host.conversation.currentId());
        if (!isCurrent()) {
            return false;
        }
        if (targetConversationId === null) {
            showUserError(i18n.t('chat.attachModal.browseNeedsConversation'));
            return false;
        }
        const targetConversation = this.#host.conversation.current();
        if (targetConversation === null) {
            showUserError(i18n.t('chat.attachModal.browseNeedsConversation'));
            return false;
        }
        await this.#host.conversation.actions.ensureConversationPersisted(targetConversation);
        if (!isCurrent() || this.#host.conversation.currentId() !== targetConversationId) {
            return false;
        }
        if (result.completedCount > result.useMaxItems) {
            showUserError(i18n.t('chat.attachModal.browseKnowledgeLimitExceeded', { count: result.useMaxItems }));
            return false;
        }
        const controller = createTrackedBrowseAbortController(this.#controllers, this.#signal);
        try {
            const payload = await this.#host.shared.api.webui.chat.attachments.knowledge.items(result.sourceConversationId, result.knowledgeAttachmentId, { limit: result.useMaxItems, status: 'completed', signal: controller.signal });
            if (controller.signal.aborted || !isCurrent()) {
                return false;
            }
            const selections = parseKnowledgeSelections(payload);
            if (selections.length === 0) {
                throw new Error('Reusable knowledge attachment has no available items');
            }
            const response = await this.#host.shared.api.webui.chat.attachments.knowledge.useItems(
                targetConversationId,
                {
                    sourceConvId: result.sourceConversationId,
                    sourceKnowledgeAttachmentId: result.knowledgeAttachmentId,
                    selections,
                    clientBatchId: createLinkedKnowledgeClientBatchId({
                        targetConversationId,
                        sourceConversationId: result.sourceConversationId,
                        sourceKnowledgeAttachmentId: result.knowledgeAttachmentId,
                        selections
                    })
                },
                { signal: controller.signal }
            );
            if (controller.signal.aborted || !isCurrent()) {
                return false;
            }
            this.#host.rag.handleKnowledgeChanged(response.summary);
            this.#host.shared.feedback.show(i18n.t('chat.attachModal.browseKnowledgeAttached'), 'success');
            return true;
        } catch (error) {
            if (controller.signal.aborted) {
                return false;
            }
            throw ensureError(error);
        } finally {
            releaseTrackedBrowseAbortController(this.#controllers, controller);
        }
    }

    abortPending(): void {
        abortTrackedBrowseAbortControllers(this.#controllers);
    }

    async #copyPreviewText(text: string): Promise<void> {
        await copyTextWithHostClipboardFeedback(
            {
                copyToClipboard: async (value, options): Promise<void> => await this.#host.presentation.copyToClipboard(value, options),
                hasClipboardSupport: () => this.#host.presentation.hasClipboardSupport(),
                showNotification: (message, type): void => this.#host.shared.feedback.show(message, type)
            },
            {
                text,
                successMessage: i18n.t('chat.message.copied'),
                errorMessage: i18n.t('chat.message.copyFailed'),
                unavailableMessage: i18n.t('chat.message.copyFailed'),
                unavailableType: 'error'
            }
        );
    }

    async #firstSelection(result: KnowledgeBrowseResult, signal: AbortSignal): Promise<KnowledgeSelection> {
        const payload = await this.#host.shared.api.webui.chat.attachments.knowledge.items(result.sourceConversationId, result.knowledgeAttachmentId, { limit: 1, status: 'completed', signal });
        const selections = parseKnowledgeSelections(payload);
        const first = selections[0];
        if (first === undefined) {
            throw new Error('Reusable knowledge attachment has no available items');
        }
        return first;
    }
}

export { ChatAttachBrowseKnowledgeOperations };
