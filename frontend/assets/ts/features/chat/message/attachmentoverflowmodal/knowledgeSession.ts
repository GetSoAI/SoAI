/* SoAI - Chat attachment overflow modal knowledge detail session [frontend/assets/ts/features/chat/message/attachmentoverflowmodal/knowledgeSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ChatKnowledgeAttachmentsApi } from '@features/chat/pagecontracts/types.ts';
import type { KnowledgeStatusFilter } from '@features/chat/message/attachmentoverflowmodal/filters.ts';
import { buildKnowledgeItemsRequestOptions, parseKnowledgeItemsPage, type KnowledgeCursor, type KnowledgeItemsQuery } from '@features/chat/message/attachmentoverflowmodal/knowledgeItems.ts';
import type { AttachmentOverflowRecord } from '@features/chat/message/attachmentoverflowmodal/records.ts';

type KnowledgeLoadMode = 'replace' | 'append';

type KnowledgeSessionSnapshot = {
    activeKnowledgeAttachmentId: string | null;
    records: readonly AttachmentOverflowRecord[];
    nextCursor: KnowledgeCursor | null;
    statusFilter: KnowledgeStatusFilter;
    query: string;
    errorMessage: string | null;
    loading: boolean;
};

type KnowledgeSessionDependencies = {
    knowledgeAttachmentsApi: Pick<ChatKnowledgeAttachmentsApi, 'items' | 'previewItem' | 'useItems'>;
    runWithBoundary: <T>(name: string, functionValue: () => Promise<T>) => Promise<T>;
    onUpdate: () => void;
    isSessionActive: (sessionToken: number) => boolean;
};

class AttachmentOverflowKnowledgeSession {
    readonly #knowledgeAttachmentsApi: Pick<ChatKnowledgeAttachmentsApi, 'items' | 'previewItem' | 'useItems'>;
    readonly #runWithBoundary: <T>(name: string, functionValue: () => Promise<T>) => Promise<T>;
    readonly #onUpdate: () => void;
    readonly #isSessionActive: (sessionToken: number) => boolean;
    #controller: AbortController | null = null;
    #requestGeneration = 0;
    #sessionToken = 0;
    #conversationId: string | null = null;
    #activeKnowledgeAttachmentId: string | null = null;
    #records: AttachmentOverflowRecord[] = [];
    #nextCursor: KnowledgeCursor | null = null;
    #failedCursor: KnowledgeCursor | null = null;
    #statusFilter: KnowledgeStatusFilter = 'all';
    #query = '';
    #errorMessage: string | null = null;
    #loading = false;

    constructor(dependencies: KnowledgeSessionDependencies) {
        this.#knowledgeAttachmentsApi = dependencies.knowledgeAttachmentsApi;
        this.#runWithBoundary = dependencies.runWithBoundary;
        this.#onUpdate = dependencies.onUpdate;
        this.#isSessionActive = dependencies.isSessionActive;
    }

    getSnapshot(): KnowledgeSessionSnapshot {
        return {
            activeKnowledgeAttachmentId: this.#activeKnowledgeAttachmentId,
            records: [...this.#records],
            nextCursor: this.#nextCursor,
            statusFilter: this.#statusFilter,
            query: this.#query,
            errorMessage: this.#errorMessage,
            loading: this.#loading
        };
    }

    reset(sessionToken: number): void {
        this.#abortActive();
        this.#sessionToken = sessionToken;
        this.#conversationId = null;
        this.#activeKnowledgeAttachmentId = null;
        this.#records = [];
        this.#nextCursor = null;
        this.#failedCursor = null;
        this.#statusFilter = 'all';
        this.#query = '';
        this.#errorMessage = null;
        this.#loading = false;
    }

    open(conversationId: string, knowledgeAttachmentId: string, sessionToken: number): void {
        this.#abortActive();
        this.#sessionToken = sessionToken;
        this.#conversationId = conversationId;
        this.#activeKnowledgeAttachmentId = knowledgeAttachmentId;
        this.#records = [];
        this.#nextCursor = null;
        this.#failedCursor = null;
        this.#errorMessage = null;
        terminateHandledPromise(this.#loadPage(null, 'replace'));
    }

    backToSummary(): void {
        this.#abortActive();
        this.#activeKnowledgeAttachmentId = null;
        this.#records = [];
        this.#nextCursor = null;
        this.#failedCursor = null;
        this.#errorMessage = null;
        this.#loading = false;
    }

    loadNextPage(): void {
        if (this.#loading || this.#errorMessage !== null || this.#nextCursor === null) {
            return;
        }
        terminateHandledPromise(this.#loadPage(this.#nextCursor, 'append'));
    }

    retryFailedPage(): void {
        if (this.#loading || this.#errorMessage === null) {
            return;
        }
        const failedCursor = this.#failedCursor;
        terminateHandledPromise(this.#loadPage(failedCursor, failedCursor === null ? 'replace' : 'append'));
    }

    reloadWithFilters(statusFilter: KnowledgeStatusFilter, query: string): void {
        if (this.#activeKnowledgeAttachmentId === null) {
            return;
        }
        this.#statusFilter = statusFilter;
        this.#query = query;
        this.#records = [];
        this.#nextCursor = null;
        this.#failedCursor = null;
        this.#errorMessage = null;
        this.#abortActive();
        terminateHandledPromise(this.#loadPage(null, 'replace'));
    }

    #beginRequest(): { generation: number; signal: AbortSignal } {
        this.#abortActive();
        this.#requestGeneration += 1;
        const controller = new AbortController();
        this.#controller = controller;
        return { generation: this.#requestGeneration, signal: controller.signal };
    }

    #abortActive(): void {
        const controller = this.#controller;
        this.#controller = null;
        this.#requestGeneration += 1;
        if (controller !== null && !controller.signal.aborted) {
            controller.abort();
        }
    }

    #isCurrent(inputArguments: { sessionToken: number; generation: number; conversationId: string; knowledgeAttachmentId: string; query: KnowledgeItemsQuery; signal: AbortSignal }): boolean {
        if (!this.#isSessionActive(inputArguments.sessionToken) || inputArguments.signal.aborted) {
            return false;
        }
        return this.#requestGeneration === inputArguments.generation && this.#conversationId === inputArguments.conversationId && this.#activeKnowledgeAttachmentId === inputArguments.knowledgeAttachmentId && this.#resolveQueryKey(this.#resolveQuery()) === this.#resolveQueryKey(inputArguments.query);
    }

    async #loadPage(cursor: KnowledgeCursor | null, mode: KnowledgeLoadMode): Promise<void> {
        const conversationId = this.#conversationId;
        const knowledgeAttachmentId = this.#activeKnowledgeAttachmentId;
        if (conversationId === null || knowledgeAttachmentId === null) {
            return;
        }
        const request = this.#beginRequest();
        const sessionToken = this.#sessionToken;
        const query = this.#resolveQuery();
        this.#loading = true;
        this.#errorMessage = null;
        this.#failedCursor = null;
        this.#onUpdate();
        try {
            const options = buildKnowledgeItemsRequestOptions(cursor, query, request.signal);
            const payload = await this.#runWithBoundary('chat:attachmentOverflowKnowledgeItems', () => this.#knowledgeAttachmentsApi.items(conversationId, knowledgeAttachmentId, options));
            if (!this.#isCurrent({ sessionToken, generation: request.generation, conversationId, knowledgeAttachmentId, query, signal: request.signal })) {
                return;
            }
            const page = parseKnowledgeItemsPage(payload, knowledgeAttachmentId);
            this.#nextCursor = page.nextCursor;
            this.#records = mode === 'replace' ? [...page.items] : [...this.#records, ...page.items];
        } catch (error) {
            if (isAbortError(error)) {
                return;
            }
            if (!this.#isCurrent({ sessionToken, generation: request.generation, conversationId, knowledgeAttachmentId, query, signal: request.signal })) {
                return;
            }
            this.#failedCursor = cursor;
            this.#errorMessage = ensureError(error).message || i18n.t('chat.attachments.modal.loadError');
        } finally {
            if (this.#isSessionActive(sessionToken) && this.#requestGeneration === request.generation) {
                this.#loading = false;
                this.#onUpdate();
            }
        }
    }

    #resolveQuery(): KnowledgeItemsQuery {
        return {
            status: this.#statusFilter === 'all' ? null : this.#statusFilter,
            query: this.#query || null
        };
    }

    #resolveQueryKey(query: KnowledgeItemsQuery): string {
        return `${query.status ?? 'all'}:${query.query ?? ''}`;
    }
}

export { AttachmentOverflowKnowledgeSession };
export type { KnowledgeSessionSnapshot };
