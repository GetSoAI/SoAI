/* SoAI - Chat composer draft write pipeline (memory + API persistence) [frontend/assets/ts/features/chat/composerdraft/composerDraftPersister.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { extractErrorCode } from '@core/errors/coerce.ts';
import { APIError } from '@core/apiError.ts';
import type { ConversationDraftResponse } from '@core/api/contracts/chatQueueDraftContracts.ts';
import { type ComposerDraftClientMutations, buildComposerDraftMutationPayloadFields, buildComposerDraftMutationRequestOptions } from '@features/chat/composerdraft/composerDraftClientMutations.ts';
import { isProjectionEmpty } from '@features/chat/composerdraft/composerDraftEntryProjection.ts';
import { resolveComposerDraftKeepaliveOptions } from '@features/chat/composerdraft/composerDraftKeepalive.ts';
import type { ComposerDraftMemoryStore } from '@features/chat/composerdraft/composerDraftMemoryStore.ts';
import type { ComposerDraftSaveChain } from '@features/chat/composerdraft/composerDraftSaveChain.ts';
import type { ComposerDraftManagerDependencies, ComposerDraftProjection } from '@features/chat/composerdraft/composerDraftTypes.ts';

interface ComposerDraftPersisterDependencies {
    readonly managerDependencies: ComposerDraftManagerDependencies;
    readonly memoryDrafts: ComposerDraftMemoryStore;
    readonly saveChain: ComposerDraftSaveChain;
    readonly mutations: ComposerDraftClientMutations;
    readonly getOwnerConversationId: () => string | null;
    readonly markApplied: (signature: string) => void;
    readonly getRevision: (conversationId: string) => number;
    readonly recordRevision: (conversationId: string, revision: number, conflicted: boolean) => void;
}

class ComposerDraftPersister {
    readonly #dependencies: ComposerDraftManagerDependencies;
    readonly #memoryDrafts: ComposerDraftMemoryStore;
    readonly #saveChain: ComposerDraftSaveChain;
    readonly #mutations: ComposerDraftClientMutations;
    readonly #getOwnerConversationId: () => string | null;
    readonly #markApplied: (signature: string) => void;
    readonly #getRevision: (conversationId: string) => number;
    readonly #recordRevision: (conversationId: string, revision: number, conflicted: boolean) => void;
    #tooLongNotificationShown = false;

    constructor(initialize: ComposerDraftPersisterDependencies) {
        this.#dependencies = initialize.managerDependencies;
        this.#memoryDrafts = initialize.memoryDrafts;
        this.#saveChain = initialize.saveChain;
        this.#mutations = initialize.mutations;
        this.#getOwnerConversationId = initialize.getOwnerConversationId;
        this.#markApplied = initialize.markApplied;
        this.#getRevision = initialize.getRevision;
        this.#recordRevision = initialize.recordRevision;
    }

    async persist(projection: ComposerDraftProjection, options: { keepalive?: boolean }): Promise<void> {
        const conversationId = projection.conversationId;
        if (!conversationId) {
            return;
        }
        if (!this.#dependencies.isConversationPersisted(conversationId)) {
            if (isProjectionEmpty(projection)) {
                this.#memoryDrafts.delete(conversationId);
                if (this.#getOwnerConversationId() === conversationId) {
                    this.#markApplied(projection.signature);
                }
                return;
            }
            this.#memoryDrafts.saveProjection(conversationId, projection, this.#dependencies.attachmentManager.getAttachments());
            if (this.#getOwnerConversationId() === conversationId) {
                this.#markApplied(projection.signature);
            }
            return;
        }
        if (projection.textTooLong) {
            if (!this.#tooLongNotificationShown) {
                this.#dependencies.showNotification(i18n.t('chat.draft.tooLong'), 'warning');
                this.#tooLongNotificationShown = true;
            }
            return;
        }
        this.#tooLongNotificationShown = false;
        if (isProjectionEmpty(projection)) {
            const deleteDraft = async (isCurrent: () => boolean): Promise<void> => {
                await this.#persistWithRevisionRetry(conversationId, projection.signature, isCurrent, async (baseRevision) => await this.#dependencies.api.delete(conversationId, buildComposerDraftMutationRequestOptions(this.#mutations.next(), baseRevision, resolveComposerDraftKeepaliveOptions(options.keepalive, undefined))));
            };
            if (options.keepalive === true) {
                await this.#saveChain.runImmediately(conversationId, deleteDraft);
                return;
            }
            await this.#saveChain.enqueue(conversationId, deleteDraft);
            return;
        }
        const saveDraft = async (isCurrent: () => boolean): Promise<void> => {
            await this.#persistWithRevisionRetry(conversationId, projection.signature, isCurrent, async (baseRevision) => {
                const payload = {
                    text: projection.text,
                    sourceText: projection.sourceText,
                    attachmentContent: projection.attachmentContent,
                    ...buildComposerDraftMutationPayloadFields(this.#mutations.next(), baseRevision)
                };
                return await this.#dependencies.api.save(conversationId, payload, resolveComposerDraftKeepaliveOptions(options.keepalive, payload));
            });
        };
        if (options.keepalive === true) {
            await this.#saveChain.runImmediately(conversationId, saveDraft);
            return;
        }
        await this.#saveChain.enqueue(conversationId, saveDraft);
    }

    async #persistWithRevisionRetry(conversationId: string, signature: string, isCurrent: () => boolean, execute: (baseRevision: number) => Promise<ConversationDraftResponse>): Promise<void> {
        let response: ConversationDraftResponse;
        let retried = false;
        try {
            response = await execute(this.#getRevision(conversationId));
        } catch (error) {
            if (extractErrorCode(error) !== 'conversation_draft_revision_conflict' || !isCurrent()) {
                throw error;
            }
            const authoritative = await this.#dependencies.api.get(conversationId);
            if (!isCurrent()) return;
            this.#recordRevision(conversationId, authoritative.revision, true);
            response = await execute(authoritative.revision);
            retried = true;
        }
        if (!isCurrent()) return;
        const knownRevision = this.#getRevision(conversationId);
        if (response.revision < knownRevision) {
            this.#recordRevision(conversationId, knownRevision, true);
            if (retried) throw this.#revisionConflict();
            response = await execute(knownRevision);
            if (!isCurrent()) return;
            if (response.revision < this.#getRevision(conversationId)) {
                throw this.#revisionConflict();
            }
        }
        this.#recordRevision(conversationId, response.revision, false);
        if (this.#getOwnerConversationId() === conversationId) {
            this.#markApplied(signature);
        }
    }

    #revisionConflict(): APIError {
        return new APIError(409, 'Conversation draft changed again during reconciliation', {
            code: 'conversation_draft_revision_conflict'
        });
    }
}

export { ComposerDraftPersister };
