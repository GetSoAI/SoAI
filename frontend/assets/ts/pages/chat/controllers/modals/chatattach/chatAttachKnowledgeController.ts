/* SoAI - Chat attach modal linked knowledge controller [frontend/assets/ts/pages/chat/controllers/modals/chatattach/chatAttachKnowledgeController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAbortError } from '@core/errors/abort.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import type { RagConfig, RagDocumentsPage } from '@features/chat/public.ts';
import type { ChatAttachKnowledgeHost } from '@pages/chat/controllers/modals/chatattach/contracts.ts';
import { acceptsKnowledgeDrop } from '@pages/chat/controllers/modals/chatattach/chatAttachDropAcceptanceController.ts';
import { bindChatAttachDropTarget } from '@pages/chat/controllers/modals/chatattach/chatAttachDropTargetController.ts';
import { resolveChatAttachDroppedPayloadType } from '@pages/chat/controllers/modals/chatattach/chatAttachDroppedPayloadController.ts';
import { readChatAttachKnowledgeCapabilities } from '@pages/chat/controllers/modals/chatattach/chatAttachKnowledgeCapabilitiesController.ts';
import { openKnowledgeDocumentsPicker, openKnowledgeFolderPicker, openKnowledgePrimaryPicker } from '@pages/chat/controllers/modals/chatattach/chatAttachKnowledgePickerController.ts';
import { ChatAttachKnowledgeRefreshLifecycleController } from '@pages/chat/controllers/modals/chatattach/ChatAttachKnowledgeRefreshLifecycleController.ts';
import { ChatAttachKnowledgeMutationController } from '@pages/chat/controllers/modals/chatattach/ChatAttachKnowledgeMutationController.ts';
import { ChatAttachKnowledgeOperations, type KnowledgeSource } from '@pages/chat/controllers/modals/chatattach/service.ts';
import { ChatAttachKnowledgeProgressController } from '@pages/chat/controllers/modals/chatattach/ChatAttachKnowledgeProgressController.ts';
import { loadChatAttachKnowledgeRefreshState } from '@pages/chat/controllers/modals/chatattach/chatAttachKnowledgeRefreshController.ts';
import type { ChatAttachKnowledgeElements } from '@pages/chat/controllers/modals/chatattach/types.ts';
import { knowledgeDocumentsSignature, renderKnowledgeDocuments, renderKnowledgeNoConversation, selectFinalizedRagDocuments, syncKnowledgeActions } from '@pages/chat/controllers/modals/chatattach/view.ts';

const POLL_DELAY_MS = 2000;

class ChatAttachKnowledgeController {
    readonly #host: ChatAttachKnowledgeHost;
    readonly #elements: ChatAttachKnowledgeElements;
    readonly #signal: AbortSignal;
    readonly #progress = new ChatAttachKnowledgeProgressController();
    readonly #refreshLifecycle: ChatAttachKnowledgeRefreshLifecycleController;
    readonly #operations: ChatAttachKnowledgeOperations;
    readonly #mutations: ChatAttachKnowledgeMutationController;
    #active = false;
    #config: RagConfig | null = null;
    #page: RagDocumentsPage | null = null;
    #lastListSignature: string | null = null;
    #unsubscribeIngestion: (() => void) | null = null;

    constructor(host: ChatAttachKnowledgeHost, elements: ChatAttachKnowledgeElements, signal: AbortSignal) {
        this.#host = host;
        this.#elements = elements;
        this.#signal = signal;
        this.#refreshLifecycle = new ChatAttachKnowledgeRefreshLifecycleController(host, signal);
        this.#operations = new ChatAttachKnowledgeOperations(host);
        this.#mutations = new ChatAttachKnowledgeMutationController({
            operations: this.#operations,
            refresh: () => this.#refresh(),
            readConversationId: () => this.#conversationId(),
            readPage: () => this.#page,
            writePageOffset: (offset) => {
                if (this.#page === null) {
                    return;
                }
                this.#page = { ...this.#page, offset };
            }
        });
        this.#bind();
        this.#syncActions();
    }

    activate(): void {
        this.#active = true;
        this.#progress.attach(this.#conversationId());
        this.#syncProgress();
        this.#subscribeIngestion();
        this.#syncActions();
        this.#host.execution.run('chat:attachKnowledgeRefresh', () => this.#refresh());
    }

    deactivate(): void {
        this.#active = false;
        this.#refreshLifecycle.invalidate();
        this.#refreshLifecycle.clearPoll();
        this.#refreshLifecycle.abortRefresh();
        this.#unsubscribeIngestion?.();
        this.#unsubscribeIngestion = null;
        this.#progress.detach();
    }

    openPrimaryPicker(): void {
        openKnowledgePrimaryPicker(this.#elements);
    }

    openDocuments(): void {
        openKnowledgeDocumentsPicker(this.#elements);
    }

    openFolder(): void {
        openKnowledgeFolderPicker(this.#elements);
    }

    async importFromFileExplorer(): Promise<void> {
        if (await this.#operations.importFromFileExplorer()) {
            await this.#refresh();
        }
    }

    async reindex(): Promise<void> {
        if (await this.#operations.reindex(this.#conversationId(), this.#config?.embeddingModel ?? null)) {
            await this.#refresh();
        }
    }

    async refresh(): Promise<void> {
        await this.#refresh();
    }

    async #refresh(): Promise<void> {
        const conversationId = this.#conversationId();
        this.#progress.setConversation(conversationId);
        if (conversationId === null) {
            this.#refreshLifecycle.abortRefresh();
            this.#renderNoConversation();
            return;
        }
        const sequence = this.#refreshLifecycle.nextSequence();
        const refreshController = this.#refreshLifecycle.replaceRefreshAbortController();
        try {
            const offset = this.#page?.offset ?? 0;
            const state = await loadChatAttachKnowledgeRefreshState(this.#host, conversationId, offset, refreshController.signal);
            if (!this.#refreshLifecycle.isCurrent(this.#active, sequence, conversationId, this.#conversationId(), refreshController.signal)) {
                return;
            }
            this.#config = state.config;
            this.#page = state.page;
            this.#render();
        } catch (error) {
            const runtimeError = ensureError(error);
            if (!this.#refreshLifecycle.isCurrent(this.#active, sequence, conversationId, this.#conversationId(), refreshController.signal) || isAbortError(runtimeError)) {
                return;
            }
            errorHandler.error('ChatAttachKnowledge', 'Failed to refresh linked knowledge', runtimeError);
            this.#host.shared.feedback.show(i18n.t('chat.configuration.notifications.ragLoadFailed'), 'error');
        } finally {
            this.#refreshLifecycle.releaseRefreshAbortController(refreshController);
        }
    }

    #bind(): void {
        this.#elements.documentInput.addEventListener('change', this.#handleDocumentInputChange, { signal: this.#signal });
        this.#elements.folderInput.addEventListener('change', this.#handleFolderInputChange, { signal: this.#signal });
        this.#elements.list.addEventListener('click', this.#handleListElementClick, { signal: this.#signal });
        bindChatAttachDropTarget({
            element: this.#elements.dropzoneButton,
            signal: this.#signal,
            setTimer: (functionValue, delayMs) => this.#host.shared.pageResources.setTimer(functionValue, delayMs),
            clearTimer: (id) => this.#host.shared.pageResources.clearTimer(id),
            isEnabled: () => {
                const capabilities = readChatAttachKnowledgeCapabilities();
                return capabilities.documentsEnabled || capabilities.foldersEnabled;
            },
            acceptsDrop: (event) => acceptsKnowledgeDrop(this.#host, event),
            onFilesDropped: (files, event) =>
                this.#host.execution.run('chat:attachKnowledgeDrop', async () => {
                    const source = resolveChatAttachDroppedPayloadType(event, files) === 'folder' ? 'folder' : 'document';
                    await this.#uploadDroppedFiles(files, source);
                })
        });
    }

    readonly #handleDocumentInputChange = (): void => {
        this.#host.execution.run('chat:attachKnowledgeDocumentsInput', () => this.#handleInput(this.#elements.documentInput, 'document'));
    };

    readonly #handleFolderInputChange = (): void => {
        this.#host.execution.run('chat:attachKnowledgeFolderInput', () => this.#handleInput(this.#elements.folderInput, 'folder'));
    };

    readonly #handleListElementClick = (event: Event): void => {
        this.#host.execution.run('chat:attachKnowledgeListClick', () => this.#handleListClick(event));
    };

    async #handleInput(input: HTMLInputElement, source: KnowledgeSource): Promise<void> {
        await this.#mutations.handleInput(input, source);
    }

    async #uploadDroppedFiles(files: File[], source: KnowledgeSource): Promise<void> {
        await this.#mutations.uploadDroppedFiles(files, source);
    }

    async #handleListClick(event: Event): Promise<void> {
        if (!(event.target instanceof Element)) {
            return;
        }
        const deleteButton = event.target.closest('.rag-document-delete');
        if (deleteButton instanceof HTMLButtonElement) {
            await this.#deleteDocument(deleteButton);
            return;
        }
        const pageButton = event.target.closest('.rag-documents-page');
        if (pageButton instanceof HTMLElement) {
            await this.#changePage(pageButton);
        }
    }

    async #deleteDocument(button: HTMLButtonElement): Promise<void> {
        await this.#mutations.deleteDocument(button);
    }

    async #changePage(button: HTMLElement): Promise<void> {
        await this.#mutations.changePage(button);
    }

    #render(): void {
        if (this.#page === null || this.#config === null) {
            return;
        }
        const finalizedDocuments = selectFinalizedRagDocuments(this.#page.documents);
        const signature = knowledgeDocumentsSignature(finalizedDocuments, this.#page);
        const rebuildList = signature !== this.#lastListSignature;
        this.#lastListSignature = signature;
        renderKnowledgeDocuments(this.#elements, this.#page, rebuildList, finalizedDocuments);
        this.#syncActions();
        this.#syncProgress();
        this.#refreshLifecycle.syncPoll(this.#active, this.#page, POLL_DELAY_MS, () => {
            this.#host.execution.run('chat:attachKnowledgePoll', () => this.#refresh());
        });
    }

    #renderNoConversation(): void {
        this.#config = null;
        this.#page = null;
        this.#lastListSignature = null;
        renderKnowledgeNoConversation(this.#elements);
        this.#syncActions();
        this.#progress.clear();
    }

    #syncProgress(): void {
        const conversationId = this.#conversationId();
        const status = conversationId === null ? null : this.#host.rag.status(conversationId);
        this.#progress.sync(
            status,
            conversationId === null
                ? null
                : () => {
                      this.#host.execution.run('chat:attachKnowledgeCancel', () => this.#host.rag.cancelForConversation(conversationId));
                  }
        );
    }

    #subscribeIngestion(): void {
        if (this.#unsubscribeIngestion !== null) {
            return;
        }
        this.#unsubscribeIngestion = this.#host.rag.subscribe(() => {
            if (!this.#active) {
                return;
            }
            this.#syncProgress();
            this.#host.execution.run('chat:attachKnowledgeIngestionRefresh', () => this.#refresh());
        });
    }

    #conversationId(): string | null {
        return this.#host.conversation.currentId();
    }

    #syncActions(): void {
        syncKnowledgeActions(this.#elements, this.#config, this.#page, readChatAttachKnowledgeCapabilities());
    }
}

export { ChatAttachKnowledgeController };
