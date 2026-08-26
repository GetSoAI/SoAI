/* SoAI - Chat preset library lifecycle and collection ownership [frontend/assets/ts/pages/chat/controllers/chatconfigurationcontroller/ChatPresetLibraryController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { publishChatPresetLibraryInvalidation, subscribeChatPresetLibraryInvalidation } from '@core/chat/chatPresetLibraryInvalidation.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { isChatPresetNameValid, serializeChatPresetRenameRequest } from '@core/api/contracts/webuiChatPresetContracts.ts';
import { FieldStateTracker } from '@core/forms/fieldStateTracker.ts';
import type { ChatPresetSections, WebuiChatPresetListResponse, WebuiChatPresetRecord } from '@core/api/contracts/webuiChatPresetContractTypes.ts';
import { type ChatPageApi, type ChatPresetSectionId } from '@features/chat/public.ts';
import { cloneChatPresetRecord, cloneChatPresetSections, executeChatPresetMutation, executeChatPresetReset, reconcileCommittedChatPresetRecord, reportChatPresetActionFailure, translateChatPresetMutationFailure, type ChatPresetMutationRequest, type ChatPresetMutationResult } from '@pages/chat/controllers/chatconfigurationcontroller/chatPresetLibraryMutationDomain.ts';
import { applyChatPresetLibraryOperationState, disconnectChatPresetLibraryPresentation, readPresetId, renderChatPresetLibrary, syncChatPresetEditorNamePresentation } from '@pages/chat/controllers/chatconfigurationcontroller/chatPresetLibraryPresentationDomain.ts';
import { createChatPresetEditorDraft, createChatPresetRecordEditorDraft, type ChatPresetConfigurationPort, type ChatPresetEditorDraft, type ChatPresetLibraryViewState } from '@pages/chat/controllers/chatconfigurationcontroller/contracts.ts';
import { executeChatPresetApply } from '@pages/chat/controllers/chatconfigurationcontroller/chatPresetApplyDomain.ts';
import { dom } from '@core/dom/dom.ts';

type ChatPresetApi = ChatPageApi['webui']['chat']['presets'];

interface ChatPresetLibraryHost {
    root: HTMLElement;
    api: ChatPresetApi;
    configuration: ChatPresetConfigurationPort;
    acquireOperation(): (() => void) | null;
    isOperationPending(): boolean;
    subscribeOperation(listener: () => void): () => void;
    runTask<Result>(operationId: string, task: () => Promise<Result> | Result): Promise<Result | undefined>;
    show(message: string, type: 'error' | 'info' | 'success' | 'warning'): void;
}

type ListResult = Readonly<{ status: 'ready'; response: WebuiChatPresetListResponse }> | Readonly<{ status: 'failed'; error: Error }>;

class ChatPresetLibraryController {
    readonly #host: ChatPresetLibraryHost;
    readonly #sequence = new SequenceToken();
    readonly #operationDisposer: () => void;
    readonly #nameTracker: FieldStateTracker;
    #session = 0;
    #invalidationEpoch = 0;
    #unsubscribe: (() => void) | null = null;
    #readSignal: AbortSignal | null = null;
    #state: ChatPresetLibraryViewState = { phase: 'idle', records: [], searchQuery: '', stale: false, lastSuccessAtMs: null, structurallyInvalidCount: 0, editor: null, sectionChoices: [], operationPending: false };

    constructor(host: ChatPresetLibraryHost) {
        this.#host = host;
        this.#nameTracker = new FieldStateTracker({ getElement: () => dom.resolve('[data-chat-preset-editor-name="true"]', host.root) });
        this.#operationDisposer = host.subscribeOperation(() => {
            this.#state = { ...this.#state, operationPending: host.isOperationPending() };
            if (this.#unsubscribe) applyChatPresetLibraryOperationState(this.#host.root, this.#state.operationPending);
        });
    }

    open(readSignal: AbortSignal): void {
        this.close();
        this.#session += 1;
        this.#readSignal = readSignal;
        this.#state = { ...this.#state, phase: 'idle', stale: false, editor: null, sectionChoices: this.#host.configuration.sectionChoices(), operationPending: this.#host.isOperationPending() };
        this.#unsubscribe = subscribeChatPresetLibraryInvalidation(() => this.#handleInvalidation(), true);
        this.refresh();
    }

    close(): void {
        this.#session += 1;
        this.#sequence.invalidate();
        this.#unsubscribe?.();
        disconnectChatPresetLibraryPresentation(this.#host.root);
        this.#unsubscribe = null;
        this.#readSignal = null;
        this.#state = { ...this.#state, editor: null, operationPending: this.#host.isOperationPending() };
    }

    dispose(): void {
        this.close();
        this.#operationDisposer();
    }
    refresh(): void {
        const session = this.#session;
        const sequence = this.#sequence.next();
        const epoch = this.#invalidationEpoch;
        const readSignal = this.#readSignal;
        this.#setState({ ...this.#state, phase: 'loading', stale: this.#state.records.length > 0 });
        void this.#host
            .runTask<ListResult>('chat:presetLibrary:refresh', async () => {
                try {
                    return { status: 'ready', response: await this.#host.api.list(readSignal ? { signal: readSignal } : {}) };
                } catch (error) {
                    const failure = ensureError(error);
                    errorHandler.warn('ChatPresetLibrary', 'Preset refresh failed', failure);
                    return { status: 'failed', error: failure };
                }
            })
            .then((result) => {
                if (!result || session !== this.#session || !this.#sequence.isActive(sequence)) return;
                if (result.status === 'failed') {
                    this.#setState({ ...this.#state, phase: 'error', stale: this.#state.records.length > 0 });
                    return;
                }
                const records = result.response.presets.map(cloneChatPresetRecord);
                this.#setState({ ...this.#state, phase: 'ready', records, stale: false, lastSuccessAtMs: Date.now(), structurallyInvalidCount: result.response.structurallyInvalidCount, editor: this.#reconcileEditor(records) });
                if (epoch !== this.#invalidationEpoch) this.refresh();
            })
            .catch((error) => errorHandler.error('ChatPresetLibrary', 'Preset refresh scheduling failed', ensureError(error)));
    }

    updateSearch(value: string): void {
        this.#setState({ ...this.#state, searchQuery: value });
    }
    enterTab(): void {
        if (!this.#unsubscribe) return;
        this.#state = { ...this.#state, sectionChoices: this.#host.configuration.sectionChoices() };
        this.refresh();
    }
    resetLibrary(): void {
        const release = this.#host.acquireOperation();
        if (!release) return;
        const session = this.#session;
        void requireDialogsService()
            .showConfirmation({ title: i18n.t('chat.configuration.presetLibrary.resetTitle'), message: i18n.t('chat.configuration.presetLibrary.resetMessage'), confirmText: i18n.t('chat.configuration.presetLibrary.resetAction'), cancelText: i18n.t('common.cancel') })
            .then(async (confirmed) => {
                if (!confirmed) return;
                const result = await this.#host.runTask('chat:presetLibrary:reset', () => executeChatPresetReset(this.#host.api));
                if (!result) return;
                if (result.status === 'failed') {
                    if (session === this.#session) this.#host.show(i18n.t('chat.configuration.presetLibrary.resetFailed'), 'error');
                    return;
                }
                publishChatPresetLibraryInvalidation(false);
                if (session === this.#session) this.#setState({ ...this.#state, phase: 'ready', records: [], stale: false, lastSuccessAtMs: Date.now(), structurallyInvalidCount: 0, editor: null });
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
        void requireDialogsService()
            .showConfirmation({ title: i18n.t('chat.configuration.presetLibrary.deleteTitle'), message: i18n.t('chat.configuration.presetLibrary.deleteMessage', { name: captured.name }), confirmText: i18n.t('common.delete'), cancelText: i18n.t('common.cancel') })
            .then((confirmed) => {
                if (!confirmed) {
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
        this.#setState({ ...this.#state, operationPending: true });
        void this.#host
            .runTask<ChatPresetMutationResult>(operationId, () => executeChatPresetMutation(this.#host.api, request))
            .then((result) => {
                if (result) this.#settleMutation(request, result, session === this.#session);
            })
            .catch((error) => reportChatPresetActionFailure(error, 'Preset mutation scheduling failed', 'chat.configuration.presetLibrary.errors.failed', (message) => this.#host.show(message, 'error')))
            .finally(() => {
                release();
                if (session === this.#session) this.#setState({ ...this.#state, operationPending: this.#host.isOperationPending() });
            });
    }

    #settleMutation(request: ChatPresetMutationRequest, result: ChatPresetMutationResult, sessionActive: boolean): void {
        if (result.status === 'failed') errorHandler.error('ChatPresetLibrary', 'Preset mutation failed', result.error);
        if (result.status === 'committed') {
            publishChatPresetLibraryInvalidation(false);
            if (!sessionActive) return;
            const records = result.record ? reconcileCommittedChatPresetRecord(this.#state.records, result.record) : this.#state.records.filter((record) => record.id !== ('presetId' in request ? request.presetId : ''));
            this.#setState({ ...this.#state, records, editor: null, stale: false, lastSuccessAtMs: Date.now() });
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
        this.#invalidationEpoch += 1;
        this.#setState({ ...this.#state, stale: this.#state.records.length > 0 });
        this.refresh();
    }

    #reconcileEditor(records: readonly WebuiChatPresetRecord[]): ChatPresetEditorDraft | null {
        const editor = this.#state.editor;
        if (!editor || editor.mode === 'create' || !editor.targetId) return editor;
        const current = records.find((record) => record.id === editor.targetId);
        if (!current) return { ...editor, targetUnavailable: true };
        return { ...editor, targetUnavailable: false, reviewRequired: current.revision !== editor.expectedRevision };
    }

    #findRecord(presetId: string | null): WebuiChatPresetRecord | null {
        return presetId ? (this.#state.records.find((record) => record.id === presetId) ?? null) : null;
    }

    #setState(state: ChatPresetLibraryViewState): void {
        this.#state = state;
        if (this.#unsubscribe) {
            renderChatPresetLibrary(this.#host.root, state);
            this.#syncNameFieldState();
        }
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
export type { ChatPresetLibraryHost };
