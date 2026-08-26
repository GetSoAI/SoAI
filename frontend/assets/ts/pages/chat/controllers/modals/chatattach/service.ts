/* SoAI - Chat attach modal linked knowledge operations [frontend/assets/ts/pages/chat/controllers/modals/chatattach/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { notifyHandledOperationError } from '@core/operationErrorNotifier.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { normalizeConversationId, normalizeFolderUploadFiles, type Conversation } from '@features/chat/public.ts';
import type { ChatAttachKnowledgeOperationsHost } from '@pages/chat/controllers/modals/chatattach/contracts.ts';

type KnowledgeSource = 'document' | 'folder';
type KnowledgeConversation = { conversation: Conversation; conversationId: string };

class ChatAttachKnowledgeOperations {
    readonly #host: ChatAttachKnowledgeOperationsHost;

    constructor(host: ChatAttachKnowledgeOperationsHost) {
        this.#host = host;
    }

    async upload(filesInput: File[], source: KnowledgeSource): Promise<boolean> {
        const files = source === 'folder' ? normalizeFolderUploadFiles(filesInput) : filesInput;
        if (files.length === 0) {
            return false;
        }
        const selection = await this.#resolveConversation();
        if (selection === null) {
            return false;
        }
        try {
            await this.#host.rag.start({
                conversationId: selection.conversationId,
                conversation: selection.conversation,
                files,
                attachmentSource: source === 'folder' ? 'knowledge_tab_folder_upload' : 'knowledge_tab_document_upload'
            });
            this.#host.shared.feedback.show(i18n.t('chat.ingestion.started', { count: files.length }), 'info');
            return true;
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.error('ChatAttachKnowledge', 'Failed to upload linked knowledge', runtimeError);
            if (!notifyHandledOperationError(runtimeError)) {
                this.#host.shared.feedback.show(i18n.t('chat.configuration.notifications.ragUploadFailed'), 'error');
            }
            return false;
        }
    }

    async importFromFileExplorer(): Promise<boolean> {
        const path = await requireDialogsService().showPrompt({
            title: i18n.t('chat.configuration.knowledge.importFromFileExplorerPromptTitle'),
            message: i18n.t('chat.configuration.knowledge.importFromFileExplorerPromptMessage'),
            defaultValue: '',
            placeholder: i18n.t('chat.configuration.knowledge.importFromFileExplorerPlaceholder'),
            inputType: 'text'
        });
        const normalizedPath = toTrimmedString(path);
        if (!normalizedPath) {
            return false;
        }
        const selection = await this.#resolvePersistedConversation();
        if (selection === null) {
            return false;
        }
        try {
            await this.#host.shared.api.webui.chat.rag.ingestFileExplorer(selection.conversationId, { path: normalizedPath, recursive: true });
            this.#host.shared.feedback.show(i18n.t('chat.configuration.notifications.ragImportQueued'), 'success');
            return true;
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.error('ChatAttachKnowledge', 'Failed to import RAG documents from File Explorer', runtimeError);
            if (!notifyHandledOperationError(runtimeError)) {
                this.#host.shared.feedback.show(i18n.t('chat.configuration.notifications.ragImportFailed'), 'error');
            }
            return false;
        }
    }

    async reindex(conversationId: string | null, embeddingModel: string | null): Promise<boolean> {
        if (conversationId === null || !embeddingModel) {
            return false;
        }
        try {
            await this.#host.shared.api.webui.chat.rag.reindex(conversationId, embeddingModel);
            this.#host.shared.feedback.show(i18n.t('chat.configuration.notifications.ragReindexQueued'), 'success');
            return true;
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.error('ChatAttachKnowledge', 'Failed to reindex RAG documents', runtimeError);
            this.#host.shared.feedback.show(i18n.t('chat.configuration.notifications.ragReindexFailed'), 'error');
            return false;
        }
    }

    async deleteDocument(conversationId: string | null, documentId: string | null): Promise<boolean> {
        if (conversationId === null || documentId === null || !documentId.trim()) {
            return false;
        }
        try {
            await this.#host.shared.api.webui.chat.rag.deleteDocument(conversationId, documentId);
            this.#host.shared.feedback.show(i18n.t('chat.configuration.notifications.ragDeleteSuccess'), 'success');
            return true;
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.error('ChatAttachKnowledge', 'Failed to delete linked knowledge document', runtimeError);
            this.#host.shared.feedback.show(i18n.t('chat.configuration.notifications.ragDeleteFailed'), 'error');
            return false;
        }
    }

    async #resolveConversation(): Promise<KnowledgeConversation | null> {
        const existingConversation = this.#host.conversation.current();
        const conversation = existingConversation ?? (await this.#host.conversation.actions.createConversation({ transferMode: 'adopt-current' }));
        const conversationId = normalizeConversationId(conversation?.id ?? null);
        if (!conversation || !conversationId) {
            this.#showNeedsConversation();
            return null;
        }
        return { conversation, conversationId };
    }

    async #resolvePersistedConversation(): Promise<KnowledgeConversation | null> {
        const selection = await this.#resolveConversation();
        if (selection === null) {
            return null;
        }
        await this.#host.conversation.actions.ensureConversationPersisted(selection.conversation);
        return selection;
    }

    #showNeedsConversation(): void {
        this.#host.shared.feedback.show(i18n.t('chat.attachModal.browseNeedsConversation'), 'error');
    }
}

export { ChatAttachKnowledgeOperations };
export type { KnowledgeSource };
