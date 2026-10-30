/* SoAI - Chat preset library lifecycle and collection ownership [frontend/assets/ts/pages/chat/controllers/chatconfigurationcontroller/ChatPresetLibraryController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getStreamResources, getStreamSubscriptions } from '@core/realtime/streammanager/public.ts';
import { CHAT_PRESETS } from '@core/realtime/streammanager/resources/ids.ts';
import { hasSameResourceAuthority } from '@core/realtime/streammanager/resources/resourceSnapshotProjection.ts';
import type { ResourceReconciliationSnapshot } from '@core/realtime/streammanager/resources/resourceReconciliationTypes.ts';
import { createDedupingOperationFailureReporter } from '@core/ui/notifications/operationFailure.ts';
import { publishChatPresetLibraryInvalidation, subscribeChatPresetLibraryInvalidation } from '@core/chat/chatPresetLibraryInvalidation.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { isChatPresetNameValid, serializeChatPresetRenameRequest } from '@core/api/contracts/webuiChatPresetContracts.ts';
import { FieldStateTracker } from '@core/forms/fieldStateTracker.ts';
import type { ChatPresetSections, WebuiChatPresetRecord } from '@core/api/contracts/webuiChatPresetContractTypes.ts';
import { type ChatPresetSectionId } from '@features/chat/public.ts';
import { cloneChatPresetRecord, cloneChatPresetSections, executeChatPresetMutation, executeChatPresetReset, reconcileCommittedChatPresetRecord, reportChatPresetActionFailure, translateChatPresetMutationFailure, type ChatPresetMutationRequest, type ChatPresetMutationResult } from '@pages/chat/controllers/chatconfigurationcontroller/chatPresetLibraryMutationDomain.ts';
import { initializeChatPresetLibraryPresentation, applyChatPresetLibraryOperationState, disconnectChatPresetLibraryPresentation, readPresetId, renderChatPresetLibrary, syncChatPresetEditorNamePresentation } from '@pages/chat/controllers/chatconfigurationcontroller/chatPresetLibraryPresentationDomain.ts';
import { createChatPresetEditorDraft, createChatPresetRecordEditorDraft, reconcileChatPresetEditorDraft, type ChatPresetLibraryHost, type ChatPresetEditorDraft, type ChatPresetLibraryViewState } from '@pages/chat/controllers/chatconfigurationcontroller/contracts.ts';
import { executeChatPresetApply } from '@pages/chat/controllers/chatconfigurationcontroller/chatPresetApplyDomain.ts';
import { dom } from '@core/dom/dom.ts';
import { bindWindowReactivation } from '@core/dom/windowReactivation.ts';
import { createLayoutFrameManager } from '@core/primitives/layoutFrameManager.ts';

class ChatPresetLibraryController {
    readonly #host: ChatPresetLibraryHost;
    #unsubscribeLibrary: (() => void) | null = null;
    #failureNotified = false;
    readonly #operationDisposer: () => void;
    readonly #nameTracker: FieldStateTracker;
    readonly #renderFrame = createLayoutFrameManager();
    #session = 0;
    #unsubscribe: (() => void) | null = null;
    #reactivationDisposer: (() => void) | null = null;
    #state: ChatPresetLibraryViewState = { phase: 'idle', records: [], searchQuery: '', stale: false, lastSuccessAtMs: null, structurallyInvalidCount: 0, editor: null, sectionChoices: [], operationPending: false };

    constructor(host: ChatPresetLibraryHost) {
        this.#host = host;
        initializeChatPresetLibraryPresentation(host.root);
        this.#nameTracker = new FieldStateTracker({ getElement: () => dom.resolve('[data-chat-preset-editor-name="true"]', host.root) });
        this.#operationDisposer = host.subscribeOperation(() => {
            this.#state = { ...this.#state, operationPending: host.isOperationPending() };
            if (this.#unsubscribe) applyChatPresetLibraryOperationState(this.#host.root, this.#state.operationPending);
        });
    }

    open(readSignal: AbortSignal): void {
        this.close();
        this.#session += 1;
        const session = this.#session;
        readSignal.addEventListener(
            'abort',
            () => {
                if (session === this.#session) this.close();
            },
            { once: true }
        );
        this.#state = { ...this.#state, phase: 'idle', stale: false, editor: null, sectionChoices: this.#host.configuration.sectionChoices(), operationPending: this.#host.isOperationPending() };
        this.#unsubscribe = subscribeChatPresetLibraryInvalidation(() => this.#handleInvalidation(), true);
        this.#reactivationDisposer = bindWindowReactivation(() => this.refresh());
        this.#unsubscribeLibrary = getStreamSubscriptions().subscribeResourceState(
            CHAT_PRESETS,
            (snapshot) => {
                if (session === this.#session) this.#receiveLibrary(snapshot);
            },
            { ensureStart: false }
        );
        this.refresh();
    }

    close(): void {
        this.#renderFrame.cancel();
        this.#failureNotified = false;
        this.#session += 1;
        this.#unsubscribeLibrary?.();
        this.#unsubscribeLibrary = null;
        this.#unsubscribe?.();
        this.#reactivationDisposer?.();
        this.#reactivationDisposer = null;
        disconnectChatPresetLibraryPresentation(this.#host.root);
        this.#unsubscribe = null;
        this.#state = { ...this.#state, editor: null, operationPending: this.#host.isOperationPending() };
    }

    dispose(): void {
        this.close();
        this.#operationDisposer();
    }
    refreshLocalization(): void {
        this.#setState(this.#state);
    }

    refresh(): void {
        if (this.#unsubscribeLibrary) getStreamResources().invalidate(CHAT_PRESETS, 'preset-library-invalidated');
    }

    #receiveLibrary(snapshot: ResourceReconciliationSnapshot): void {
        if (snapshot.status === 'ready') {
            const library = getStreamResources().getResource(CHAT_PRESETS);
            if (library === null || library !== snapshot.value) return;
            const records = library.presets.map(cloneChatPresetRecord);
            this.#failureNotified = false;
            this.#setState({ ...this.#state, phase: 'ready', records, stale: false, lastSuccessAtMs: getStreamResources().getResource(CHAT_PRESETS, { state: true })?.updatedAt ?? null, structurallyInvalidCount: library.structurallyInvalidCount, editor: reconcileChatPresetEditorDraft(this.#state.editor, records) });
            return;
        }
        const loading = snapshot.status === 'initializing' || snapshot.status === 'recovering';
        this.#setState({ ...this.#state, phase: loading ? 'loading' : 'error', stale: this.#state.lastSuccessAtMs !== null });
        if (snapshot.status === 'error' && snapshot.error && !this.#failureNotified) {
            this.#failureNotified = true;
            createDedupingOperationFailureReporter({ host: { showNotification: (message, type) => this.#host.show(message, type), handleError: (error) => errorHandler.warn('ChatPresetLibrary', 'Preset refresh failed', error) } }).report(snapshot.error, { errorMessage: i18n.t('chat.configuration.presetLibrary.loadFailed'), rawMessage: true, context: 'Preset library' });
        }
    }

    updateSearch(value: string): void {
        this.#setState({ ...this.#state, searchQuery: value });
    }
    enterTab(): void {
        if (!this.#unsubscribe) return;
        this.#state = { ...this.#state, sectionChoices: this.#host.configuration.sectionChoices() };
        this.#setState(this.#state);
    }
    resetLibrary(): void {
        const release = this.#host.acquireOperation();
        if (!release) return;
        const session = this.#session;
        void requireDialogsService()
            .showConfirmation({ title: i18n.t('chat.configuration.presetLibrary.resetTitle'), message: i18n.t('chat.configuration.presetLibrary.resetMessage'), confirmText: i18n.t('chat.configuration.presetLibrary.resetAction'), cancelText: i18n.t('common.cancel') })
            .then(async (confirmed) => {
                if (!confirmed || session !== this.#session) return;
                const authority = getStreamResources().getReconciliationSnapshot(CHAT_PRESETS);
                const result = await this.#host.runTask('chat:presetLibrary:reset', () => executeChatPresetReset(this.#host.api));
                if (!result) return;
                if (result.status === 'failed') {
                    if (session === this.#session) this.#host.show(i18n.t('chat.configuration.presetLibrary.resetFailed'), 'error');
                    return;
                }
                const project = session === this.#session && hasSameResourceAuthority(authority, getStreamResources().getReconciliationSnapshot(CHAT_PRESETS));
                if (session === this.#session) this.refresh();
                publishChatPresetLibraryInvalidation(false);
                if (project) this.#setState({ ...this.#state, phase: 'ready', records: [], stale: true, structurallyInvalidCount: 0, editor: null });
                if (session === this.#session) this.#host.show(i18n.t('chat.configuration.presetLibrary.resetSuccess', { count: result.deleted }), 'success');
            })
            .catch((error) => reportChatPresetActionFailure(error, 'Preset library reset failed', 'chat.configuration.presetLibrary.resetFailed', (message) => this.#host.show(message, 'error')))
            .finally(release);
    }
    updateEditorName(value: string): void {
        const editor = this.#state.editor;
        if (!editor) return;
        this.#state = { ...this.#state, editor: { ...editor, name: value, nameConflict: false } };
        if (!this.#unsubscribe) return;
        syncChatPresetEditorNamePresentation(this.#host.root, this.#state);
        this.#syncNameFieldState();
    }

    updateEditorSection(sectionId: ChatPresetSectionId, selected: boolean): void {
        const editor = this.#state.editor;
        if (!editor || editor.mode === 'rename') return;
        const sections = new Set(editor.selectedSections);
        if (selected) sections.add(sectionId);
        else sections.delete(sectionId);
        this.#setState({ ...this.#state, editor: { ...editor, selectedSections: sections } });
    }

    newPreset(): void {
        const selected = new Set(
            this.#host.configuration
                .sectionChoices()
                .filter((choice) => choice.eligible && choice.hydrated)
                .map((choice) => choice.id)
        );
        this.#setState({ ...this.#state, editor: createChatPresetEditorDraft('create', null, selected), sectionChoices: this.#host.configuration.sectionChoices() });
    }

    editPreset(actionElement: HTMLElement, mode: 'rename' | 'replace'): void {
        const record = this.#findRecord(readPresetId(actionElement));
        if (!record || this.#state.stale) return;
        const sectionChoices = this.#host.configuration.sectionChoices();
        this.#setState({ ...this.#state, editor: createChatPresetRecordEditorDraft(mode, cloneChatPresetRecord(record), sectionChoices), sectionChoices });
    }

    cancelEditor(): void {
        this.#setState({ ...this.#state, editor: null });
    }

    reviewEditor(): void {
        const editor = this.#state.editor;
        const record = editor?.targetId ? this.#findRecord(editor.targetId) : null;
        if (!editor || editor.mode === 'create' || !record) return;
        this.#setState({ ...this.#state, editor: createChatPresetRecordEditorDraft(editor.mode, cloneChatPresetRecord(record), this.#state.sectionChoices) });
    }

    submitEditor(): void {
        const editor = this.#state.editor;
        if (!editor || !isChatPresetNameValid(editor.name) || editor.nameConflict || !this.#nameTracker.isValid() || editor.targetUnavailable || editor.reviewRequired || this.#state.stale) return;
        const release = this.#host.acquireOperation();
        if (!release) return;
        const captured = { ...editor, selectedSections: new Set(editor.selectedSections) };
        let request: ChatPresetMutationRequest | null = null;
        try {
            const serializedName = serializeChatPresetRenameRequest({ expectedRevision: 1, name: captured.name })['name'];
            if (typeof serializedName !== 'string') throw new Error('Preset name is invalid.');
            const name = serializedName;
            if (captured.mode === 'rename') {
                if (!captured.targetId || !captured.expectedRevision) throw new Error('Rename preset target is unavailable.');
                request = { type: 'rename', presetId: captured.targetId, expectedRevision: captured.expectedRevision, name };
            } else {
                const snapshot = this.#host.configuration.snapshot(captured.selectedSections);
                if (snapshot.status === 'invalid') throw new Error(snapshot.message);
                if (snapshot.prunedValues.length > 0) this.#host.show(i18n.t('chat.configuration.presetLibrary.editor.prunedValues', { count: snapshot.prunedValues.length }), 'warning');
                request = captured.mode === 'create' ? { type: 'create', name, sections: cloneChatPresetSections(snapshot.sections) } : this.#replaceRequest(captured, name, snapshot.sections);
            }
        } catch (error) {
            release();
            reportChatPresetActionFailure(ensureError(error), 'Preset editor preparation failed', 'chat.configuration.presetLibrary.errors.failed', (message) => this.#host.show(message, 'error'));
        }
        if (!request) return;
        this.#runMutation(`chat:presetLibrary:${request.type}`, request, release);
    }

    removePreset(actionElement: HTMLElement): void {
        const record = this.#findRecord(readPresetId(actionElement));
        if (!record || this.#state.stale) return;
        const release = this.#host.acquireOperation();
        if (!release) return;
        const captured = cloneChatPresetRecord(record);
        const session = this.#session;
        void requireDialogsService()
            .showConfirmation({ title: i18n.t('chat.configuration.presetLibrary.deleteTitle'), message: i18n.t('chat.configuration.presetLibrary.deleteMessage', { name: captured.name }), confirmText: i18n.t('common.delete'), cancelText: i18n.t('common.cancel') })
            .then((confirmed) => {
                if (!confirmed || session !== this.#session) {
                    release();
                    return;
                }
                this.#runMutation('chat:presetLibrary:delete', { type: 'delete', presetId: captured.id, expectedRevision: captured.revision }, release);
            })
            .catch((error) => {
                release();
                reportChatPresetActionFailure(error, 'Preset delete confirmation failed', 'chat.configuration.presetLibrary.errors.failed', (message) => this.#host.show(message, 'error'));
            });
    }

    applyPreset(actionElement: HTMLElement): void {
        const record = this.#findRecord(readPresetId(actionElement));
        if (!record || !record.applicable || this.#state.stale) return;
        const release = this.#host.acquireOperation();
        if (!release) return;
        const session = this.#session;
        const captured = cloneChatPresetRecord(record);
        void executeChatPresetApply({ record: captured, configuration: this.#host.configuration, isSessionActive: () => session === this.#session, show: (message, type) => this.#host.show(message, type) })
            .catch((error) => reportChatPresetActionFailure(error, 'Preset application scheduling failed', 'chat.configuration.presetLibrary.applyFailed', (message) => this.#host.show(message, 'error')))
            .finally(release);
    }

    hasOpenEditor(): boolean {
        return this.#state.editor !== null;
    }
    #runMutation(operationId: string, request: ChatPresetMutationRequest, release: () => void): void {
        const session = this.#session;
        const authority = getStreamResources().getReconciliationSnapshot(CHAT_PRESETS);
        this.#setState({ ...this.#state, operationPending: true });
        void this.#host
            .runTask<ChatPresetMutationResult>(operationId, () => executeChatPresetMutation(this.#host.api, request))
            .then((result) => {
                if (result) this.#settleMutation(request, result, session === this.#session, authority);
            })
            .catch((error) => reportChatPresetActionFailure(error, 'Preset mutation scheduling failed', 'chat.configuration.presetLibrary.errors.failed', (message) => this.#host.show(message, 'error')))
            .finally(() => {
                release();
                if (session === this.#session) this.#setState({ ...this.#state, operationPending: this.#host.isOperationPending() });
            });
    }

    #settleMutation(request: ChatPresetMutationRequest, result: ChatPresetMutationResult, sessionActive: boolean, authority: ResourceReconciliationSnapshot): void {
        if (result.status === 'failed') errorHandler.error('ChatPresetLibrary', 'Preset mutation failed', result.error);
        if (result.status === 'committed') {
            publishChatPresetLibraryInvalidation(false);
            if (!sessionActive) return;
            const project = hasSameResourceAuthority(authority, getStreamResources().getReconciliationSnapshot(CHAT_PRESETS));
            this.refresh();
            const records = !project ? this.#state.records : result.record ? reconcileCommittedChatPresetRecord(this.#state.records, result.record) : this.#state.records.filter((record) => record.id !== ('presetId' in request ? request.presetId : ''));
            this.#setState({ ...this.#state, records, editor: null, stale: true });
            this.#host.show(i18n.t('chat.configuration.presetLibrary.saved'), 'success');
            return;
        }
        if (!sessionActive) return;
        const editor = this.#state.editor;
        if (result.status === 'name_conflict' && editor) this.#setState({ ...this.#state, editor: { ...editor, nameConflict: true } });
        else if (result.status === 'revision_conflict' && editor) this.#setState({ ...this.#state, editor: { ...editor, reviewRequired: true } });
        else if (result.status === 'not_found' && editor && 'presetId' in request && editor.targetId === request.presetId) this.#setState({ ...this.#state, editor: null });
        this.#host.show(translateChatPresetMutationFailure(result.status), result.status === 'ambiguous' ? 'warning' : 'error');
        if (result.status === 'revision_conflict' || result.status === 'not_found' || result.status === 'ambiguous') this.refresh();
    }

    #replaceRequest(editor: ChatPresetEditorDraft, name: string, sections: ChatPresetSections): ChatPresetMutationRequest {
        if (!editor.targetId || !editor.expectedRevision) throw new Error('Replace preset target is unavailable.');
        return { type: 'replace', presetId: editor.targetId, expectedRevision: editor.expectedRevision, name, sections: cloneChatPresetSections(sections) };
    }

    #handleInvalidation(): void {
        this.#setState({ ...this.#state, stale: this.#state.records.length > 0 });
        this.refresh();
    }

    #findRecord(presetId: string | null): WebuiChatPresetRecord | null {
        return presetId ? (this.#state.records.find((record) => record.id === presetId) ?? null) : null;
    }

    #setState(state: ChatPresetLibraryViewState): void {
        this.#state = state;
        this.#renderFrame.queue(() => {
            if (this.#unsubscribe) {
                renderChatPresetLibrary(this.#host.root, this.#state);
                this.#syncNameFieldState();
            }
        });
    }

    #syncNameFieldState(): void {
        const editor = this.#state.editor;
        if (!editor) {
            this.#nameTracker.clearAll();
            return;
        }
        this.#nameTracker.update('preset-name', { currentValue: editor.name, originalValue: editor.originalName });
        const message = editor.nameConflict ? i18n.t('chat.configuration.presetLibrary.errors.name_conflict') : editor.name.length > 0 && !isChatPresetNameValid(editor.name) ? i18n.t('chat.configuration.presetLibrary.editor.nameInvalid') : null;
        this.#nameTracker.setInvalid('preset-name', message);
    }
}

export { ChatPresetLibraryController };
