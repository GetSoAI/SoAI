/* SoAI - Chat composer draft persistence manager [frontend/assets/ts/features/chat/composerdraft/ChatComposerDraftManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { createAbortSignalScope, isAbortError } from '@core/errors/abort.ts';
import type { ConversationDraftChangedEvent } from '@core/realtime/eventcontracts/chatControlContracts.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';
import { ComposerDraftClientMutations } from '@features/chat/composerdraft/composerDraftClientMutations.ts';
import { buildProjectionSignature, isProjectionEmpty, projectComposerDraft } from '@features/chat/composerdraft/composerDraftEntryProjection.ts';
import { ComposerDraftMemoryStore } from '@features/chat/composerdraft/composerDraftMemoryStore.ts';
import { ComposerDraftLoadRegistry } from '@features/chat/composerdraft/composerDraftLoadRegistry.ts';
import { emptyParsedComposerDraft, parseComposerDraftResponse } from '@features/chat/composerdraft/composerDraftParsing.ts';
import { ComposerDraftPersister } from '@features/chat/composerdraft/composerDraftPersister.ts';
import { ComposerDraftSaveChain } from '@features/chat/composerdraft/composerDraftSaveChain.ts';
import { presentComposerDraftRestoreFailure, trackComposerDraftTaskFailure } from '@features/chat/composerdraft/composerDraftTaskLogging.ts';
import { ComposerDraftOwnershipState, type ComposerDraftOwnershipSnapshot, type ComposerDraftTransferMode } from '@features/chat/composerdraft/ComposerDraftOwnershipState.ts';
import { ComposerDraftRevisionState } from '@features/chat/composerdraft/ComposerDraftRevisionState.ts';
import { ComposerDraftDebounce } from '@features/chat/composerdraft/ComposerDraftDebounce.ts';
import type { ComposerDraftLoadSettlement, ComposerDraftManagerDependencies, ComposerDraftProjection, ComposerDraftTransferTicket, ParsedComposerDraft } from '@features/chat/composerdraft/composerDraftTypes.ts';

class ChatComposerDraftManager {
    readonly #dependencies: ComposerDraftManagerDependencies;
    readonly #saveChain = new ComposerDraftSaveChain();
    readonly #memoryDrafts = new ComposerDraftMemoryStore();
    readonly #draftLoads = new ComposerDraftLoadRegistry();
    readonly #mutations = new ComposerDraftClientMutations();
    readonly #revisions: ComposerDraftRevisionState;
    readonly #debounce: ComposerDraftDebounce;
    readonly #persister: ComposerDraftPersister;
    readonly #ownership: ComposerDraftOwnershipState;
    #disposed = false;
    #applying = false;
    #appliedSignature = buildProjectionSignature('', '', []);
    #pendingFlush: { conversationId: string; signature: string; keepalive: boolean; promise: Promise<void> } | null = null;
    #unsubscribeAttachments: (() => void) | null = null;
    #unsubscribeDraftEvents: (() => void) | null = null;
    constructor(dependencies: ComposerDraftManagerDependencies) {
        this.#dependencies = dependencies;
        this.#ownership = new ComposerDraftOwnershipState(normalizeConversationId(dependencies.getCurrentConversationId()));
        this.#revisions = new ComposerDraftRevisionState(dependencies.showNotification);
        this.#debounce = new ComposerDraftDebounce(dependencies);
        this.#persister = new ComposerDraftPersister({
            managerDependencies: dependencies,
            memoryDrafts: this.#memoryDrafts,
            saveChain: this.#saveChain,
            mutations: this.#mutations,
            getOwnerConversationId: () => this.#ownership.conversationId,
            markApplied: (signature) => {
                if (this.#projectCurrent().signature === signature) {
                    this.#appliedSignature = signature;
                }
            },
            getRevision: (conversationId) => this.#revisions.get(conversationId),
            recordRevision: (conversationId, revision, conflicted) => this.#revisions.record(conversationId, revision, conflicted)
        });
    }

    ensureInitialized(): void {
        if (this.#disposed || this.#unsubscribeAttachments !== null) {
            return;
        }
        this.#unsubscribeAttachments = this.#dependencies.attachmentManager.subscribeDraftChanges(() => this.notifyComposerChanged());
        this.#unsubscribeDraftEvents = this.#dependencies.subscribeDraftChanged((event) => this.#handleDraftChangedEvent(event));
    }

    notifyComposerChanged(): void {
        if (this.#disposed || this.#applying) {
            return;
        }
        this.#ownership.noteMutation();
        if (this.#ownership.phase === 'loading') return;
        const projection = this.#projectCurrent();
        if (projection.signature === this.#appliedSignature) {
            return;
        }
        this.#debounce.clear();
        if (isProjectionEmpty(projection)) {
            trackComposerDraftTaskFailure(this.flushNow('empty'), this.#dependencies, 'Failed to delete empty composer draft');
            return;
        }
        this.#debounce.schedule(() => {
            trackComposerDraftTaskFailure(this.flushNow('debounce'), this.#dependencies, 'Failed to save composer draft');
        });
    }

    async flushNow(reason: string, options: { keepalive?: boolean } = {}): Promise<void> {
        if (this.#disposed && reason !== 'dispose') {
            return;
        }
        this.#debounce.clear();
        const projection = this.#projectCurrent();
        if (this.#ownership.phase === 'loading' && !this.#ownership.isLocalProjectionAuthoritative() && projection.signature === this.#appliedSignature) return;
        const pendingFlush = this.#pendingFlush;
        const hasConflictingPendingFlush = pendingFlush?.conversationId === projection.conversationId && pendingFlush.signature !== projection.signature;
        if (projection.signature === this.#appliedSignature && !hasConflictingPendingFlush) {
            return;
        }
        const keepalive = options.keepalive === true;
        if (pendingFlush?.conversationId === projection.conversationId && pendingFlush.signature === projection.signature && (!keepalive || pendingFlush.keepalive)) {
            await pendingFlush.promise;
            return;
        }
        if (!projection.conversationId) {
            return;
        }
        let trackedPromise: Promise<void>;
        const persistence = this.#persister.persist(projection, options);
        trackedPromise = persistence.finally(() => {
            if (this.#pendingFlush?.promise === trackedPromise) {
                this.#pendingFlush = null;
            }
        });
        this.#pendingFlush = {
            conversationId: projection.conversationId,
            signature: projection.signature,
            keepalive,
            promise: trackedPromise
        };
        await trackedPromise;
    }

    beginComposerTransfer(nextConversationId: string | null, options: { mode: ComposerDraftTransferMode; signal?: AbortSignal }): ComposerDraftTransferTicket {
        this.ensureInitialized();
        const normalizedNextId = normalizeConversationId(nextConversationId);
        if (this.#ownership.conversationId && (this.#ownership.isLocalProjectionAuthoritative() || this.#projectCurrent().signature !== this.#appliedSignature)) {
            this.#debounce.clear();
            trackComposerDraftTaskFailure(this.#persister.persist(this.#projectCurrent(), {}), this.#dependencies, 'Failed to save composer draft during transfer');
        }
        const ownership = this.#ownership.begin(normalizedNextId, options.mode);
        if (options.mode === 'restore') this.#applyDraft(emptyParsedComposerDraft(), ownership);
        const transferAbortController = new AbortController();
        const transferSignalScope = createAbortSignalScope([options.signal, transferAbortController.signal]);
        const draftPromise = this.#draftLoads
            .load(transferSignalScope.signal, async (signal) => await this.#readDraft(normalizedNextId, signal))
            .then(
                (draft): ComposerDraftLoadSettlement => ({ status: 'ready', draft }),
                (error): ComposerDraftLoadSettlement => ({ status: 'failed', error: ensureError(error) })
            )
            .finally(transferSignalScope.cleanup);
        let completionPromise: Promise<void> | null = null;
        return {
            complete: async () => {
                if (transferAbortController.signal.aborted) return;
                completionPromise ??= this.#completeTransfer(ownership, draftPromise, transferSignalScope.signal);
                await completionPromise;
            },
            cancel: () => {
                if (transferAbortController.signal.aborted) return;
                transferAbortController.abort();
                this.#ownership.finish(ownership, true);
            }
        };
    }

    discardConversation(conversationId: string): void {
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId) return;
        this.#memoryDrafts.delete(normalizedConversationId);
        this.#revisions.discard(normalizedConversationId);
        if (this.#ownership.discard(normalizedConversationId)) this.#appliedSignature = buildProjectionSignature('', '', []);
    }

    dispose(): void {
        if (this.#disposed) {
            return;
        }
        trackComposerDraftTaskFailure(this.flushNow('dispose'), this.#dependencies, 'Failed to flush composer draft during disposal');
        this.#disposed = true;
        this.#debounce.clear();
        this.#draftLoads.clear();
        this.#unsubscribeAttachments?.();
        this.#unsubscribeDraftEvents?.();
        this.#unsubscribeAttachments = null;
        this.#unsubscribeDraftEvents = null;
    }

    #projectCurrent(): ComposerDraftProjection {
        const conversationId = normalizeConversationId(this.#ownership.conversationId ?? this.#dependencies.getCurrentConversationId());
        return projectComposerDraft({
            conversationId,
            text: this.#dependencies.readText(),
            sourceText: this.#dependencies.readSourceText(),
            attachments: this.#dependencies.attachmentManager.getAttachments()
        });
    }

    async #readDraft(conversationId: string | null, signal?: AbortSignal): Promise<ParsedComposerDraft> {
        if (!conversationId) {
            return emptyParsedComposerDraft();
        }
        if (!this.#dependencies.isConversationPersisted(conversationId)) {
            return this.#memoryDrafts.read(conversationId);
        }
        await this.#saveChain.wait(conversationId);
        const response = await this.#dependencies.api.get(conversationId, signal === undefined ? {} : { signal });
        return parseComposerDraftResponse(conversationId, response);
    }

    async #completeTransfer(ownership: ComposerDraftOwnershipSnapshot, draftPromise: Promise<ComposerDraftLoadSettlement>, signal?: AbortSignal): Promise<void> {
        let restoreFailurePresented = false;
        try {
            const settlement = await draftPromise;
            if (this.#disposed || !this.#ownership.isCurrent(ownership, signal)) return;
            let loadResult: { draft: ParsedComposerDraft; degraded: boolean };
            if (settlement.status === 'failed') {
                if (isAbortError(settlement.error)) return;
                presentComposerDraftRestoreFailure(this.#dependencies, 'Failed to restore composer draft', settlement.error);
                restoreFailurePresented = true;
                loadResult = { draft: emptyParsedComposerDraft(), degraded: true };
            } else {
                loadResult = { draft: settlement.draft, degraded: false };
            }
            const conversationId = ownership.conversationId;
            const deferredRevision = this.#ownership.highestDeferredRevision(ownership);
            if (conversationId !== null && deferredRevision > loadResult.draft.revision) {
                const reread = await this.#readDraft(conversationId, signal);
                if (this.#disposed || !this.#ownership.isCurrent(ownership, signal)) return;
                const latestDeferredRevision = this.#ownership.highestDeferredRevision(ownership);
                if (reread.revision < latestDeferredRevision) {
                    this.#revisions.record(conversationId, latestDeferredRevision, true);
                    const localProjectionAuthoritative = this.#ownership.isLocalProjectionAuthoritative();
                    if (localProjectionAuthoritative) this.#appliedSignature = reread.signature;
                    this.#ownership.finish(ownership, true);
                    if (localProjectionAuthoritative) this.#scheduleCurrentPersistence();
                    else terminateHandledPromise(this.#reloadDraftFromEvent(conversationId));
                    return;
                }
                loadResult = { draft: reread, degraded: false };
            }
            if (conversationId !== null) this.#revisions.record(conversationId, loadResult.draft.revision, false);
            const surfaceChanged = this.#ownership.surfaceChangedSince(ownership) || this.#projectCurrent().signature !== this.#appliedSignature;
            if (ownership.mode === 'adopt-current' || surfaceChanged) {
                if (conversationId !== null && surfaceChanged) this.#revisions.record(conversationId, loadResult.draft.revision, true);
                this.#appliedSignature = loadResult.draft.signature;
                this.#ownership.finish(ownership, loadResult.degraded);
                this.#scheduleCurrentPersistence();
                return;
            }
            try {
                this.#applyDraft(loadResult.draft, ownership);
                this.#ownership.finish(ownership, loadResult.degraded);
            } catch (error) {
                const caughtError = ensureError(error);
                presentComposerDraftRestoreFailure(this.#dependencies, 'Failed to apply composer draft', caughtError);
                this.#ownership.finish(ownership, true);
            }
        } catch (error) {
            if (isAbortError(error) || !this.#ownership.isCurrent(ownership, signal)) return;
            if (!restoreFailurePresented) presentComposerDraftRestoreFailure(this.#dependencies, 'Failed to reconcile composer draft during transfer', ensureError(error));
            const localProjectionAuthoritative = this.#ownership.isLocalProjectionAuthoritative();
            this.#ownership.finish(ownership, true);
            if (localProjectionAuthoritative) this.#scheduleCurrentPersistence();
        }
    }

    #scheduleCurrentPersistence(): void {
        const projection = this.#projectCurrent();
        if (projection.conversationId === null || projection.signature === this.#appliedSignature) return;
        trackComposerDraftTaskFailure(this.#persister.persist(projection, {}), this.#dependencies, 'Failed to save composer draft after ownership transfer');
    }

    async #reloadDraftFromEvent(conversationId: string): Promise<void> {
        const ownership = this.#ownership.snapshot();
        try {
            const draft = await this.#draftLoads.load(undefined, async (signal) => await this.#readDraft(conversationId, signal));
            if (this.#disposed || !this.#ownership.isCurrent(ownership) || this.#ownership.conversationId !== conversationId || this.#ownership.phase === 'loading') return;
            if (this.#projectCurrent().signature !== this.#appliedSignature) {
                this.#revisions.record(conversationId, draft.revision, true);
                return;
            }
            this.#applyDraft(draft, ownership);
        } catch (error) {
            if (!isAbortError(error) && !this.#disposed && this.#ownership.isCurrent(ownership)) presentComposerDraftRestoreFailure(this.#dependencies, 'Failed to apply composer draft event', ensureError(error));
        }
    }

    #applyDraft(draft: ParsedComposerDraft, ownership: ComposerDraftOwnershipSnapshot): void {
        try {
            if (!this.#ownership.isCurrent(ownership)) return;
            this.#dependencies.validateSourceProjection(draft.text, draft.sourceText, draft.soaiPathRecords);
            if (!this.#ownership.isCurrent(ownership)) return;
            this.#applying = true;
            this.#dependencies.restoreSourceProjection(draft.text, draft.sourceText, draft.soaiPathRecords);
            this.#dependencies.setText(draft.text);
            this.#dependencies.attachmentManager.checkoutAttachments();
            this.#dependencies.attachmentManager.restoreAttachments(draft.attachments);
            this.#dependencies.attachmentManager.addResolvedSoaiPathRecords(draft.soaiPathRecords);
            this.#dependencies.refreshComposerUi();
            this.#dependencies.noteInputDraftChanged(draft.text);
            this.#appliedSignature = draft.signature;
            if (this.#ownership.conversationId !== null) this.#revisions.record(this.#ownership.conversationId, draft.revision, false);
        } finally {
            this.#applying = false;
        }
    }

    #handleDraftChangedEvent(changedEvent: ConversationDraftChangedEvent): void {
        if (changedEvent.convId !== this.#ownership.conversationId) {
            return;
        }
        const currentRevision = this.#revisions.get(changedEvent.convId);
        if (changedEvent.revision <= currentRevision) return;
        if (this.#ownership.phase === 'loading') {
            if (changedEvent.clientId === this.#mutations.clientId) this.#revisions.record(changedEvent.convId, changedEvent.revision, false);
            this.#ownership.deferRevision(changedEvent.revision);
            return;
        }
        if (changedEvent.clientId === this.#mutations.clientId) {
            this.#revisions.record(changedEvent.convId, changedEvent.revision, false);
            return;
        }
        const projection = this.#projectCurrent();
        if (projection.signature !== this.#appliedSignature) {
            this.#revisions.record(changedEvent.convId, changedEvent.revision, true);
            return;
        }
        if (changedEvent.deleted) {
            try {
                this.#applyDraft(emptyParsedComposerDraft(changedEvent.revision), this.#ownership.snapshot());
            } catch (error) {
                const caughtError = ensureError(error);
                presentComposerDraftRestoreFailure(this.#dependencies, 'Failed to apply deleted composer draft event', caughtError);
            }
            return;
        }
        terminateHandledPromise(this.#reloadDraftFromEvent(changedEvent.convId));
    }
}

export { ChatComposerDraftManager };
