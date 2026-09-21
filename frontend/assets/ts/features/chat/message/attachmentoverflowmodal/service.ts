/* SoAI - Chat message attachment overflow modal service [frontend/assets/ts/features/chat/message/attachmentoverflowmodal/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import type { KnowledgeAttachmentSummary } from '@core/api/contracts/webuiAttachmentContracts.ts';
import { isString } from '@core/typeGuards.ts';
import { CHAT_ATTACHMENT_OVERFLOW_MODAL_ID } from '@features/chat/modals/constants.ts';
import type { ChatKnowledgeAttachmentsApi, ChatSoaiPathsApi } from '@features/chat/pagecontracts/types.ts';
import { AttachmentOverflowAutoPager } from '@features/chat/message/attachmentoverflowmodal/autoPager.ts';
import { countAttachmentOverflowRecords } from '@features/chat/message/attachmentoverflowmodal/counts.ts';
import { filterAttachmentOverflowRecords, type AttachmentOverflowCategoryFilter, type KnowledgeStatusFilter } from '@features/chat/message/attachmentoverflowmodal/filters.ts';
import { AttachmentOverflowInteractionController } from '@features/chat/message/attachmentoverflowmodal/interactionController.ts';
import { AttachmentOverflowKnowledgeFirstPreview } from '@features/chat/message/attachmentoverflowmodal/knowledgeFirstPreview.ts';
import { AttachmentOverflowKnowledgePreview } from '@features/chat/message/attachmentoverflowmodal/knowledgePreview.ts';
import { AttachmentOverflowKnowledgeSession } from '@features/chat/message/attachmentoverflowmodal/knowledgeSession.ts';
import { AttachmentOverflowListRenderer } from '@features/chat/message/attachmentoverflowmodal/listRenderer.ts';
import { buildAttachmentOverflowRecords, type AttachmentOverflowRecord } from '@features/chat/message/attachmentoverflowmodal/records.ts';
import type { AttachmentOverflowShowArguments } from '@features/chat/message/attachmentoverflowmodal/showArgs.ts';
import { AttachmentOverflowModalShell } from '@features/chat/message/attachmentoverflowmodal/view.ts';
import type { CopyActionDependencies } from '@features/chat/message/messageCopyNotifications.ts';
import { ChatSoaiPathContentPreview } from '@features/chat/message/soaiPathContentPreview.ts';

const CONTENT_ID = `${CHAT_ATTACHMENT_OVERFLOW_MODAL_ID}-content`;

interface AttachmentOverflowModalDependencies extends CopyActionDependencies {
    knowledgeAttachmentsApi: Pick<ChatKnowledgeAttachmentsApi, 'items' | 'previewItem' | 'useItems'>;
    soaiPathsApi: Pick<ChatSoaiPathsApi, 'preview' | 'read' | 'download' | 'open' | 'token'>;
    getAttachmentDraftRevision: () => number;
    onKnowledgeAttachmentChanged: (summary: KnowledgeAttachmentSummary) => void;
}

class ChatAttachmentOverflowModal {
    readonly #runWithBoundary: CopyActionDependencies['runWithBoundary'];
    readonly #getAttachmentDraftRevision: () => number;
    readonly #listRenderer = new AttachmentOverflowListRenderer();
    readonly #autoPager = new AttachmentOverflowAutoPager(() => this.#handleAutoPageReveal());
    readonly #knowledgeSession: AttachmentOverflowKnowledgeSession;
    readonly #knowledgeFirstPreview: AttachmentOverflowKnowledgeFirstPreview;
    readonly #knowledgePreview: AttachmentOverflowKnowledgePreview;
    readonly #soaiPathPreview: ChatSoaiPathContentPreview;
    readonly #interactions: AttachmentOverflowInteractionController;
    #shell: AttachmentOverflowModalShell | null = null;
    #allRecords: AttachmentOverflowRecord[] = [];
    #conversationId: string | null = null;
    #activeTab: AttachmentOverflowCategoryFilter = 'all';
    #sessionToken = 0;

    constructor(dependencies: AttachmentOverflowModalDependencies) {
        this.#runWithBoundary = dependencies.runWithBoundary;
        this.#getAttachmentDraftRevision = dependencies.getAttachmentDraftRevision;
        this.#knowledgeSession = new AttachmentOverflowKnowledgeSession({
            knowledgeAttachmentsApi: dependencies.knowledgeAttachmentsApi,
            runWithBoundary: (name, functionValue) => this.#runWithBoundary(name, functionValue),
            onUpdate: () => this.#render(),
            isSessionActive: (sessionToken) => this.#isSessionActive(sessionToken)
        });
        this.#knowledgeFirstPreview = new AttachmentOverflowKnowledgeFirstPreview({
            knowledgeAttachmentsApi: dependencies.knowledgeAttachmentsApi,
            runWithBoundary: (name, functionValue) => this.#runWithBoundary(name, functionValue),
            isSessionActive: (sessionToken) => this.#isSessionActive(sessionToken),
            hasClipboardSupport: () => dependencies.hasClipboardSupport(),
            copyToClipboard: (text, options) => dependencies.copyToClipboard(text, options),
            showNotification: (message, type) => dependencies.showNotification(message, type),
            onKnowledgeAttachmentChanged: (summary) => dependencies.onKnowledgeAttachmentChanged(summary)
        });
        this.#knowledgePreview = new AttachmentOverflowKnowledgePreview({
            knowledgeAttachmentsApi: dependencies.knowledgeAttachmentsApi,
            runWithBoundary: (name, functionValue) => this.#runWithBoundary(name, functionValue),
            isSessionActive: (sessionToken) => this.#isSessionActive(sessionToken),
            getAttachmentDraftRevision: () => this.#getAttachmentDraftRevision(),
            hasClipboardSupport: () => dependencies.hasClipboardSupport(),
            copyToClipboard: (text, options) => dependencies.copyToClipboard(text, options),
            showNotification: (message, type) => dependencies.showNotification(message, type),
            onKnowledgeAttachmentChanged: (summary) => dependencies.onKnowledgeAttachmentChanged(summary)
        });
        this.#soaiPathPreview = new ChatSoaiPathContentPreview({
            soaiPathsApi: dependencies.soaiPathsApi,
            runWithBoundary: (name, functionValue) => this.#runWithBoundary(name, functionValue),
            hasClipboardSupport: () => dependencies.hasClipboardSupport(),
            copyToClipboard: (text, options) => dependencies.copyToClipboard(text, options),
            showNotification: (message, type) => dependencies.showNotification(message, type)
        });
        this.#interactions = new AttachmentOverflowInteractionController({
            onTab: (tab) => this.#selectTab(tab),
            onRetry: () => this.#knowledgeSession.retryFailedPage(),
            onKnowledgePreview: (actionElement) => this.#openKnowledgePreview(actionElement),
            onKnowledgePreviewFirst: (actionElement) => this.#openKnowledgeFirstPreview(actionElement),
            onSoaiPathPreview: (actionElement) => this.#openSoaiPathPreview(actionElement),
            onSearchSubmit: (query) => this.#reloadKnowledgeSearch(query),
            onStatusChange: (status) => this.#reloadKnowledgeStatus(status)
        });
    }

    dispose(): void {
        this.#sessionToken += 1;
        this.#knowledgeFirstPreview.reset();
        this.#knowledgeSession.reset(this.#sessionToken);
        this.#knowledgePreview.reset();
        this.#soaiPathPreview.reset();
        this.#autoPager.dispose();
        this.#listRenderer.dispose();
        this.#interactions.dispose();
        this.#shell = null;
    }

    show(inputArguments: AttachmentOverflowShowArguments): void {
        const records = buildAttachmentOverflowRecords(inputArguments.conversationId, inputArguments.segments);
        const presenter = requireModalPresenter();
        const modal = presenter.requireElement(CHAT_ATTACHMENT_OVERFLOW_MODAL_ID);
        modal.removeEventListener('core.modal.close', this.#handleModalClose);
        modal.addEventListener('core.modal.close', this.#handleModalClose, { once: true });
        this.#interactions.attach(modal);
        this.#sessionToken += 1;
        this.#conversationId = inputArguments.conversationId;
        this.#activeTab = 'all';
        this.#allRecords = records;
        this.#knowledgeFirstPreview.reset();
        this.#knowledgeSession.reset(this.#sessionToken);
        this.#knowledgePreview.reset();
        this.#soaiPathPreview.reset();
        this.#autoPager.dispose();
        this.#render();
        presenter.open(CHAT_ATTACHMENT_OVERFLOW_MODAL_ID);
        const knowledgeAttachmentId = inputArguments.knowledgeAttachmentId;
        if (isString(knowledgeAttachmentId) && knowledgeAttachmentId.trim()) {
            this.#showKnowledgeAttachment(knowledgeAttachmentId.trim());
        }
    }

    #render(): void {
        const content = dom.resolve(`#${CONTENT_ID}`);
        const tabsHost = dom.resolve(modalUiSelector(CHAT_ATTACHMENT_OVERFLOW_MODAL_ID, 'tabs'));
        if (!(content instanceof HTMLElement) || !(tabsHost instanceof HTMLElement)) {
            throw new Error('Attachment overflow modal content is missing');
        }
        const shell = this.#resolveShell(content, tabsHost);
        const knowledge = this.#knowledgeSession.getSnapshot();
        const records = knowledge.activeKnowledgeAttachmentId !== null ? knowledge.records : filterAttachmentOverflowRecords(this.#allRecords, this.#activeTab);
        shell.update({
            activeTab: this.#activeTab,
            tabCounts: countAttachmentOverflowRecords(this.#allRecords),
            knowledgeActive: knowledge.activeKnowledgeAttachmentId !== null,
            statusFilter: knowledge.statusFilter,
            query: knowledge.query,
            errorMessage: knowledge.errorMessage,
            loadingKnowledge: knowledge.loading,
            hasNextKnowledgePage: knowledge.nextCursor !== null,
            recordsCount: records.length
        });
        this.#listRenderer.update({ shell, records });
        this.#autoPager.update(shell.scrollRoot, shell.sentinel, this.#shouldEnableAutoPaging());
    }

    #resolveShell(content: HTMLElement, tabsHost: HTMLElement): AttachmentOverflowModalShell {
        if (this.#shell === null || !this.#shell.list.isConnected) {
            this.#shell = new AttachmentOverflowModalShell(content, tabsHost);
        }
        return this.#shell;
    }

    #selectTab(tab: AttachmentOverflowCategoryFilter): void {
        if (tab !== 'knowledge') {
            this.#knowledgeSession.backToSummary();
        }
        this.#activeTab = tab;
        this.#render();
    }

    #openKnowledgePreview(actionElement: HTMLElement): void {
        const knowledge = this.#knowledgeSession.getSnapshot();
        this.#knowledgePreview.openFromActionElement({
            actionElement,
            conversationId: this.#conversationId,
            knowledgeAttachmentId: knowledge.activeKnowledgeAttachmentId,
            records: knowledge.records,
            sessionToken: this.#sessionToken,
            draftRevision: this.#getAttachmentDraftRevision()
        });
    }

    #openKnowledgeFirstPreview(actionElement: HTMLElement): void {
        this.#knowledgeFirstPreview.openFromActionElement({
            actionElement,
            conversationId: this.#conversationId,
            sessionToken: this.#sessionToken
        });
    }

    #openSoaiPathPreview(actionElement: HTMLElement): void {
        const collectionId = actionElement.dataset['collectionId'];
        const record = isString(collectionId) ? this.#allRecords.find((item) => item.id === collectionId.trim()) : null;
        const conversationId = this.#conversationId;
        if (record === undefined || record === null || conversationId === null || record.soaiPathContentPart === null) {
            return;
        }
        const sessionToken = this.#sessionToken;
        this.#soaiPathPreview.open({
            conversationId,
            title: record.title,
            contentPart: record.soaiPathContentPart,
            isCurrent: () => this.#isSessionActive(sessionToken)
        });
    }

    #reloadKnowledgeSearch(query: string): void {
        const snapshot = this.#knowledgeSession.getSnapshot();
        this.#knowledgeSession.reloadWithFilters(snapshot.statusFilter, query);
    }

    #reloadKnowledgeStatus(status: KnowledgeStatusFilter): void {
        const query = this.#knowledgeSession.getSnapshot().query;
        this.#knowledgeSession.reloadWithFilters(status, query);
    }

    readonly #handleModalClose = (): void => {
        this.#sessionToken += 1;
        this.#knowledgeFirstPreview.reset();
        this.#knowledgeSession.reset(this.#sessionToken);
        this.#knowledgePreview.reset();
        this.#soaiPathPreview.reset();
        this.#autoPager.dispose();
        this.#listRenderer.dispose();
    };

    #showKnowledgeAttachment(knowledgeAttachmentId: string): void {
        this.#activeTab = 'knowledge';
        const conversationId = this.#conversationId;
        if (!isString(conversationId) || !conversationId.trim()) {
            throw new Error('Attachment overflow modal requires a conversation id');
        }
        this.#knowledgeSession.open(conversationId.trim(), knowledgeAttachmentId, this.#sessionToken);
    }

    #handleAutoPageReveal(): void {
        if (!this.#shouldEnableAutoPaging()) {
            return;
        }
        this.#knowledgeSession.loadNextPage();
    }

    #shouldEnableAutoPaging(): boolean {
        const knowledge = this.#knowledgeSession.getSnapshot();
        return this.#activeTab === 'knowledge' && knowledge.activeKnowledgeAttachmentId !== null && knowledge.nextCursor !== null && !knowledge.loading && knowledge.errorMessage === null && this.#isSessionActive(this.#sessionToken);
    }

    #isSessionActive(sessionToken: number): boolean {
        return sessionToken === this.#sessionToken && requireModalPresenter().isOpen(CHAT_ATTACHMENT_OVERFLOW_MODAL_ID);
    }
}

export { ChatAttachmentOverflowModal };
