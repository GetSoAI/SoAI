/* SoAI - Chat knowledge attachment draft cache manager [frontend/assets/ts/pages/chat/controllers/chatmessagesendingcontroller/knowledgeAttachmentDraftCacheManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { KnowledgeAttachmentCollectionResponse, KnowledgeAttachmentSummary } from '@core/api/contracts/webuiAttachmentContracts.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { selectLatestKnowledgeAttachmentSummary } from '@features/chat/public.ts';
import type { MessageSendingHost } from '@pages/chat/controllers/chatmessagesendingcontroller/types.ts';

type KnowledgeChangedApplication = {
    conversationId: string;
    notificationSummary: KnowledgeAttachmentSummary | null;
};

class KnowledgeAttachmentDraftCache {
    readonly #itemsByConversationId = new Map<string, KnowledgeAttachmentSummary[]>();
    readonly #loadedConversationIds = new Set<string>();
    readonly #dirtyWhileRefreshingConversationIds = new Set<string>();
    readonly #refreshingConversationIds = new Set<string>();
    readonly #removedRevisionsByConversationId = new Map<string, Map<string, number>>();
    readonly #revisionsByConversationId = new Map<string, Map<string, number>>();

    get(conversationId: string): KnowledgeAttachmentSummary[] {
        return [...(this.#itemsByConversationId.get(conversationId) ?? [])];
    }

    beginRefresh(conversationId: string): boolean {
        if (this.#loadedConversationIds.has(conversationId) || this.#refreshingConversationIds.has(conversationId)) return false;
        this.#refreshingConversationIds.add(conversationId);
        return true;
    }

    finishRefresh(conversationId: string): boolean {
        this.#refreshingConversationIds.delete(conversationId);
        if (!this.#dirtyWhileRefreshingConversationIds.has(conversationId)) return false;
        this.#dirtyWhileRefreshingConversationIds.delete(conversationId);
        this.#loadedConversationIds.delete(conversationId);
        return true;
    }

    clearConversation(conversationId: string): void {
        this.#itemsByConversationId.delete(conversationId);
        this.#loadedConversationIds.delete(conversationId);
        this.#dirtyWhileRefreshingConversationIds.delete(conversationId);
        this.#refreshingConversationIds.delete(conversationId);
        this.#removedRevisionsByConversationId.delete(conversationId);
        this.#revisionsByConversationId.delete(conversationId);
    }

    applyDraftPayload(conversationId: string, payload: KnowledgeAttachmentCollectionResponse): void {
        const currentItems = this.#itemsByConversationId.get(conversationId) ?? [];
        const currentRevisions = this.#revisionsByConversationId.get(conversationId) ?? new Map<string, number>();
        const removedRevisions = this.#removedRevisionsByConversationId.get(conversationId) ?? new Map<string, number>();
        const nextItems: KnowledgeAttachmentSummary[] = [];
        const nextRemovedRevisions = new Map<string, number>(removedRevisions);
        const nextRevisions = new Map<string, number>();
        const includedSummaryIds = new Set<string>();
        for (const summary of payload.items) {
            const summaryId = summary.knowledgeAttachmentId;
            const nextRevision = summary.attachmentRevision;
            const currentRevision = currentRevisions.get(summaryId);
            const removedRevision = removedRevisions.get(summaryId);
            if (removedRevision !== undefined && nextRevision <= removedRevision) continue;
            if (currentRevision !== undefined && nextRevision < currentRevision) {
                const currentItem = currentItems.find((candidate) => candidate.knowledgeAttachmentId === summaryId);
                if (currentItem !== undefined) {
                    nextItems.push(currentItem);
                    nextRevisions.set(summaryId, currentRevision);
                    includedSummaryIds.add(summaryId);
                    continue;
                }
            }
            nextItems.push(summary);
            nextRevisions.set(summaryId, nextRevision);
            nextRemovedRevisions.delete(summaryId);
            includedSummaryIds.add(summaryId);
        }
        if (this.#dirtyWhileRefreshingConversationIds.has(conversationId)) {
            for (const currentItem of currentItems) {
                const summaryId = currentItem.knowledgeAttachmentId;
                if (includedSummaryIds.has(summaryId)) continue;
                nextItems.push(currentItem);
                const currentRevision = currentRevisions.get(summaryId);
                if (currentRevision !== undefined) nextRevisions.set(summaryId, currentRevision);
            }
        }
        this.#itemsByConversationId.set(conversationId, nextItems);
        if (nextRemovedRevisions.size === 0) this.#removedRevisionsByConversationId.delete(conversationId);
        else this.#removedRevisionsByConversationId.set(conversationId, nextRemovedRevisions);
        this.#revisionsByConversationId.set(conversationId, nextRevisions);
        this.#loadedConversationIds.add(conversationId);
    }

    applyChangedSummary(summary: KnowledgeAttachmentSummary): KnowledgeChangedApplication {
        const conversationId = summary.convId;
        const matchingCurrent = (this.#itemsByConversationId.get(conversationId) ?? []).find((item) => item.knowledgeAttachmentId === summary.knowledgeAttachmentId || Boolean(item.clientBatchId && item.clientBatchId === summary.clientBatchId));
        const reconciled = matchingCurrent === undefined ? summary : selectLatestKnowledgeAttachmentSummary(matchingCurrent, summary);
        const summaryId = reconciled.knowledgeAttachmentId;
        const summaryRevision = reconciled.attachmentRevision;
        const revisions = this.#revisionsByConversationId.get(conversationId) ?? new Map<string, number>();
        const currentRevision = revisions.get(summaryId);
        if (currentRevision !== undefined && summaryRevision < currentRevision) {
            return { conversationId, notificationSummary: null };
        }
        const current = this.#itemsByConversationId.get(conversationId) ?? [];
        const withoutSummary = current.filter((item) => item !== matchingCurrent && item.knowledgeAttachmentId !== summaryId);
        this.#itemsByConversationId.set(conversationId, reconciled.state === 'draft' ? [...withoutSummary, reconciled] : withoutSummary);
        const removedRevisions = this.#removedRevisionsByConversationId.get(conversationId) ?? new Map<string, number>();
        if (reconciled.state === 'draft') {
            revisions.set(summaryId, summaryRevision);
            this.#revisionsByConversationId.set(conversationId, revisions);
            removedRevisions.delete(summaryId);
        } else {
            revisions.delete(summaryId);
            if (revisions.size === 0) this.#revisionsByConversationId.delete(conversationId);
            else this.#revisionsByConversationId.set(conversationId, revisions);
            removedRevisions.set(summaryId, summaryRevision);
        }
        if (removedRevisions.size === 0) this.#removedRevisionsByConversationId.delete(conversationId);
        else this.#removedRevisionsByConversationId.set(conversationId, removedRevisions);
        if (this.#refreshingConversationIds.has(conversationId)) this.#dirtyWhileRefreshingConversationIds.add(conversationId);
        return {
            conversationId,
            notificationSummary: summary.attachmentRevision < reconciled.attachmentRevision ? null : reconciled
        };
    }

    clear(): void {
        this.#itemsByConversationId.clear();
        this.#loadedConversationIds.clear();
        this.#dirtyWhileRefreshingConversationIds.clear();
        this.#refreshingConversationIds.clear();
        this.#removedRevisionsByConversationId.clear();
        this.#revisionsByConversationId.clear();
    }
}

const runKnowledgeAttachmentDraftCacheRefresh = async (inputArguments: { cache: KnowledgeAttachmentDraftCache; host: MessageSendingHost; conversationId: string; onUpdated: () => void }): Promise<void> => {
    let refreshFinished = false;
    try {
        const payload = await inputArguments.host.platform.runWithBoundary('chat:listDraftKnowledgeAttachmentsPreview', () => inputArguments.host.services.getChatApi().webui.chat.attachments.knowledge.draft(inputArguments.conversationId, { previewLimit: 6, signal: inputArguments.host.platform.getRuntimeAbortSignal() ?? undefined }));
        inputArguments.cache.applyDraftPayload(inputArguments.conversationId, payload);
        const shouldRetry = inputArguments.cache.finishRefresh(inputArguments.conversationId);
        refreshFinished = true;
        inputArguments.onUpdated();
        if (shouldRetry) refreshKnowledgeAttachmentDraftCache(inputArguments);
    } catch (error) {
        const runtimeError = ensureError(error);
        if (!isAbortError(runtimeError)) inputArguments.host.platform.handleError(runtimeError, i18n.t('chat.errors.syncFailed'), { notify: false });
    } finally {
        if (!refreshFinished && inputArguments.cache.finishRefresh(inputArguments.conversationId)) refreshKnowledgeAttachmentDraftCache(inputArguments);
    }
};

const refreshKnowledgeAttachmentDraftCache = (inputArguments: { cache: KnowledgeAttachmentDraftCache; host: MessageSendingHost; conversationId: string; onUpdated: () => void }): void => {
    if (!inputArguments.cache.beginRefresh(inputArguments.conversationId)) return;
    void runKnowledgeAttachmentDraftCacheRefresh(inputArguments).catch((error) => {
        const runtimeError = ensureError(error);
        if (!isAbortError(runtimeError)) inputArguments.host.platform.handleError(runtimeError, i18n.t('chat.errors.syncFailed'), { notify: false });
        if (inputArguments.cache.finishRefresh(inputArguments.conversationId)) refreshKnowledgeAttachmentDraftCache(inputArguments);
    });
};

export { KnowledgeAttachmentDraftCache, refreshKnowledgeAttachmentDraftCache };
