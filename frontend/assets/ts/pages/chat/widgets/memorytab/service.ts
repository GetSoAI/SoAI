/* SoAI - Chat memory library lifecycle and reconciliation [frontend/assets/ts/pages/chat/widgets/memorytab/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getAuthManager } from '@core/auth/public.ts';
import { APIError } from '@core/apiError.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { createDedupingOperationFailureReporter } from '@core/ui/notifications/operationFailure.ts';
import { LatestRequestController } from '@core/concurrency/latestRequest.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { dispatchCustomEvent, getEventHub } from '@core/environment/public.ts';
import { dom } from '@core/dom/dom.ts';
import { bindPageActionDispatcher } from '@core/dom/dataActionBinding.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { bindWindowReactivation } from '@core/dom/windowReactivation.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { CONTENT_PREVIEW_MODAL_ID } from '@core/ui/modals/contentpreview/constants.ts';
import { i18n } from '@core/i18n/index.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { wallClockMs } from '@core/time/clock.ts';
import { requireContentPreviewModalService } from '@core/ui/modals/contentpreview/service.ts';
import type { ManagedMemoryEntry } from '@core/api/contracts/webuiMemoryContracts.ts';
import { CHAT_ACTIONS, CHAT_MEMORY_UPDATED_EVENT, CHAT_MEMORY_RECORD_MODAL_ID, isChatActionId } from '@features/chat/public.ts';
import type { MemoryApi, MemoryLibraryState, MemoryMutationHost } from '@pages/chat/widgets/memorytab/contracts.ts';
import { deleteMemoryRecord, memoryFailureMessage, openMemoryTextEditor } from '@pages/chat/widgets/memorytab/memoryMutationDomain.ts';
import { compareMemoryEntryOrder, disconnectMemoryPresentation, initializeMemoryPresentation, memoryMatchesQuery, memoryStaleMessage, renderMemoryLibrary } from '@pages/chat/widgets/memorytab/memoryPresentationDomain.ts';
import { editMemoryRelationship } from '@pages/chat/widgets/memorytab/memoryRelationshipDomain.ts';
import { openMemoryRecordManagement, renderMemoryRecordManagement } from '@pages/chat/widgets/memorytab/memoryRecordManagementDomain.ts';

interface MemoryLibraryHost {
    root: HTMLElement;
    api: MemoryApi;
    openProfile(): void;
    runTask(operation: string, task: () => Promise<void>): void;
    show: MemoryMutationHost['show'];
}

class MemoryLibraryController {
    readonly #host: MemoryLibraryHost;
    readonly #reads = new LatestRequestController();
    readonly #session = new SequenceToken();
    readonly #openings = new SequenceToken();
    readonly #refreshes = new SequenceToken();
    readonly #resources = new ResourceTracker();
    #recordContent: HTMLElement | null = null;
    #recordEntry: ManagedMemoryEntry | null = null;
    #recordEvents: AbortController | null = null;
    #active = false;
    #account: number | null = null;
    #renderPending = false;
    #committedRefreshPending = false;
    #state: MemoryLibraryState = { snapshot: null, phase: 'idle', stale: false, refreshedAt: null, query: '', opening: false, editorOpen: false, pending: false };

    constructor(host: MemoryLibraryHost) {
        this.#host = host;
        initializeMemoryPresentation(host.root);
        const invalidateAccount = (): void => {
            this.#closeRecord();
            if (this.#state.editorOpen) requireModalPresenter().close(CONTENT_PREVIEW_MODAL_ID, { force: true, reason: 'account-changed' });
            this.#reads.invalidate();
            this.#session.invalidate();
            this.#account = getAuthManager().getCurrentUser()?.id ?? null;
            this.#state = { ...this.#state, snapshot: null, query: '', stale: false, phase: 'idle', refreshedAt: null, opening: false, editorOpen: false, pending: false };
            this.#scheduleRender();
            if (this.#active && this.#account !== null) this.#host.runTask('chat:memoryAccountChanged', () => this.refresh().then(() => {}));
        };
        this.#resources.addEventListener(getEventHub(), 'core.modal.close', (event) => {
            if (event.target instanceof HTMLElement && event.target.id === CHAT_MEMORY_RECORD_MODAL_ID) this.#releaseRecord();
            if (event.target instanceof HTMLElement && event.target.id === CONTENT_PREVIEW_MODAL_ID) {
                this.#state = { ...this.#state, editorOpen: false };
                this.#scheduleRender();
            }
        });
        this.#resources.track(getAuthManager().onLogout(invalidateAccount));
        this.#resources.track(getAuthManager().onLogin(invalidateAccount));
        this.#resources.track(
            bindWindowReactivation(() => {
                if (this.#active) this.#host.runTask('chat:memoryReactivation', () => this.refresh().then(() => {}));
            })
        );
        this.#resources.addEventListener(getEventHub(), CHAT_MEMORY_UPDATED_EVENT, () => {
            this.#reads.invalidate();
            const session = this.#session.value;
            const committed = this.#committedRefreshPending;
            this.#committedRefreshPending = false;
            if (this.#active)
                this.#host.runTask('chat:memoryInvalidation', async () => {
                    if (this.#isCurrent(session)) await this.refresh(committed);
                });
        });
    }
    open(signal: AbortSignal): void {
        this.close();
        this.#active = true;
        this.#account = getAuthManager().getCurrentUser()?.id ?? null;
        const session = this.#session.value;
        signal.addEventListener(
            'abort',
            () => {
                if (this.#session.isActive(session)) this.close();
            },
            { once: true }
        );
        this.#scheduleRender();
    }
    close(): void {
        this.#closeRecord();
        this.#active = false;
        this.#session.invalidate();
        this.#openings.invalidate();
        this.#reads.invalidate();
        this.#state = { ...this.#state, opening: false, pending: false };
        disconnectMemoryPresentation(this.#host.root);
    }
    dispose(): void {
        this.close();
        terminateHandledPromise(this.#resources.cleanup());
    }
    updateSearch(query: string): void {
        this.#state = { ...this.#state, query };
        this.#scheduleRender();
    }
    readonly refresh = async (afterCommit = false): Promise<boolean> => {
        if (!this.#active || this.#account === null) return false;
        const session = this.#session.value;
        const refresh = this.#refreshes.next();
        this.#state = { ...this.#state, phase: 'loading' };
        this.#scheduleRender();
        try {
            const committed = await this.#reads.runLatest(async (run) => {
                const snapshot = await this.#host.api.list({ signal: run.signal });
                if (!run.isCurrent() || !this.#isCurrent(session)) return false;
                this.#state = { ...this.#state, snapshot, phase: 'ready', stale: false, refreshedAt: wallClockMs() };
                if (this.#recordEntry) {
                    this.#recordEntry = snapshot.entries.find((entry) => entry.entity.id === this.#recordEntry?.entity.id) ?? null;
                    if (!this.#recordEntry) this.#closeRecord();
                }
                this.#scheduleRender();
                return true;
            });
            if (committed !== true && this.#isCurrent(session) && this.#refreshes.isActive(refresh) && this.#state.phase === 'loading') {
                this.#state = { ...this.#state, phase: this.#state.snapshot ? 'ready' : 'idle' };
                this.#scheduleRender();
            }
            return committed === true;
        } catch (error) {
            if (!this.#isCurrent(session)) return false;
            this.#state = { ...this.#state, phase: 'failed', stale: this.#state.snapshot !== null };
            this.#scheduleRender();
            this.#mutationHost().report(ensureError(error), afterCommit ? i18n.t('chat.memory.library.savedRefreshNeeded') : i18n.t('chat.memory.errors.loadFailed'));
            return false;
        }
    };
    handleAction(element: HTMLElement): void {
        if (!this.#active || this.#state.pending || this.#state.opening) return;
        const action = element.dataset['action'];
        if (action === CHAT_ACTIONS.ADD_MEMORY) {
            if (requireContentPreviewModalService().isOpen()) return;
            openMemoryTextEditor(this.#mutationHost(), null, null);
            this.#state = { ...this.#state, editorOpen: true };
            this.#scheduleRender();
            return;
        }
        const entry = this.#recordContent?.contains(element) ? this.#recordEntry : this.#state.snapshot?.entries.find((candidate) => candidate.entity.id === element.dataset['memoryId']);
        if (!entry) return;
        const childId = element.dataset['memoryChildId'] ?? '';
        if (action === CHAT_ACTIONS.OPEN_MEMORY_PROFILE) {
            this.#host.openProfile();
            return;
        }
        if (action === CHAT_ACTIONS.VIEW_MEMORY || action === CHAT_ACTIONS.MANAGE_MEMORY || action === CHAT_ACTIONS.EDIT_MEMORY || action === CHAT_ACTIONS.EDIT_MEMORY_OBSERVATION) {
            if (requireContentPreviewModalService().isOpen()) return;
            const host = this.#mutationHost();
            this.#state = { ...this.#state, opening: true };
            this.#scheduleRender();
            const mode = action === CHAT_ACTIONS.VIEW_MEMORY ? 'view' : action === CHAT_ACTIONS.MANAGE_MEMORY ? 'record' : action === CHAT_ACTIONS.EDIT_MEMORY ? 'entryEdit' : 'edit';
            const opening = this.#openings.next();
            this.#host.runTask('chat:memoryEditor', () => this.#openEditor(host, entry, childId || (entry.observations[0]?.id ?? null), mode, opening));
            return;
        }
        if (action !== CHAT_ACTIONS.EDIT_MEMORY_RELATION && action !== CHAT_ACTIONS.DELETE_MEMORY_RELATION && action !== CHAT_ACTIONS.DELETE_MEMORY_OBSERVATION && action !== CHAT_ACTIONS.DELETE_MEMORY) return;
        this.#reads.invalidate();
        this.#state = { ...this.#state, pending: true };
        this.#scheduleRender();
        const host = this.#mutationHost();
        this.#host.runTask('chat:memoryMutation', async () => {
            if (!host.isCurrent()) return;
            try {
                if (action === CHAT_ACTIONS.EDIT_MEMORY_RELATION) await editMemoryRelationship(host, entry, childId, this.#state.snapshot?.entries ?? []);
                else await deleteMemoryRecord(host, entry, action === CHAT_ACTIONS.DELETE_MEMORY_OBSERVATION ? { type: 'observation', id: childId } : action === CHAT_ACTIONS.DELETE_MEMORY_RELATION ? { type: 'relation', id: childId } : null);
            } finally {
                if (host.isCurrent()) {
                    this.#state = { ...this.#state, pending: false };
                    this.#scheduleRender();
                }
            }
        });
    }
    #isCurrent(session: number): boolean {
        return this.#active && this.#session.isActive(session) && this.#account !== null && this.#account === (getAuthManager().getCurrentUser()?.id ?? null);
    }
    #mutationHost(): MemoryMutationHost {
        const session = this.#session.value;
        const show: MemoryMutationHost['show'] = (message, type) => {
            if (this.#isCurrent(session)) this.#host.show(message, type);
        };
        const reportUnexpectedFailure = (error: Error): void => {
            if (!(error instanceof APIError)) errorHandler.error('MemoryLibrary', 'Unexpected memory operation failure', error);
        };
        const failures = createDedupingOperationFailureReporter({
            host: {
                showNotification: show,
                handleError: reportUnexpectedFailure
            }
        });
        return {
            api: this.#host.api,
            show,
            report: (error, message = memoryFailureMessage(error)) => {
                if (!this.#isCurrent(session)) {
                    reportUnexpectedFailure(error);
                    return;
                }
                if (error instanceof APIError && (error.code === 'memory_revision_changed' || error.code === 'memory_entry_missing')) {
                    this.#reads.invalidate();
                    this.#state = { ...this.#state, stale: this.#state.snapshot !== null, phase: this.#state.snapshot ? 'ready' : 'failed' };
                    this.#scheduleRender();
                }
                failures.report(error, { errorMessage: message, rawMessage: true, context: 'Memory library operation' });
            },
            isCurrent: () => this.#isCurrent(session),
            committed: (entry) => {
                this.#reads.invalidate();
                if (this.#isCurrent(session)) {
                    this.#state = { ...this.#state, stale: true };
                    if (entry && this.#state.snapshot) this.#state = { ...this.#state, snapshot: { ...this.#state.snapshot, entries: [entry, ...this.#state.snapshot.entries.filter((candidate) => candidate.entity.id !== entry.entity.id)].sort(compareMemoryEntryOrder) }, stale: true };
                    if (entry && !memoryMatchesQuery(entry, this.#state.query)) this.#host.show(i18n.t('chat.memory.library.savedHidden'), 'info');
                    this.#committedRefreshPending = true;
                    this.#scheduleRender();
                }
                dispatchCustomEvent(CHAT_MEMORY_UPDATED_EVENT, {});
            }
        };
    }
    async #openEditor(host: MemoryMutationHost, entry: ManagedMemoryEntry, observationId: string | null, mode: 'view' | 'edit' | 'record' | 'entryEdit', opening: number): Promise<void> {
        if (!host.isCurrent() || !this.#openings.isActive(opening)) return;
        try {
            const current = await this.#host.api.read(entry.entity.id);
            if (!host.isCurrent() || !this.#openings.isActive(opening) || requireContentPreviewModalService().isOpen()) return;
            const recordMode = mode === 'record' || (mode === 'entryEdit' && current.observations.length > 1);
            const selectedFactId = mode === 'entryEdit' ? (current.observations[0]?.id ?? null) : observationId;
            if (current.revision !== entry.revision) {
                this.#reads.invalidate();
                this.#state = { ...this.#state, stale: this.#state.snapshot !== null, phase: 'ready' };
            }
            if (!recordMode && selectedFactId !== null && !current.observations.some((fact) => fact.id === selectedFactId)) {
                this.#host.show(i18n.t('chat.memory.errors.missing'), 'warning');
                return;
            }
            if (host.isCurrent() && !requireContentPreviewModalService().isOpen()) {
                if (recordMode) {
                    this.#reads.invalidate();
                    this.#recordEntry = current;
                    this.#recordContent = openMemoryRecordManagement(current);
                    this.#recordEvents?.abort();
                    this.#recordEvents = new AbortController();
                    bindPageActionDispatcher({ root: this.#recordContent, signal: this.#recordEvents.signal, label: 'Memory record', isAction: isChatActionId, events: { click: { onAction: ({ actionElement }) => this.handleAction(actionElement) } } });
                    this.#state = { ...this.#state, phase: 'ready' };
                } else if (mode === 'entryEdit' && current.observations[0]?.profileField) {
                    this.#host.openProfile();
                } else {
                    openMemoryTextEditor(host, current, mode === 'view' && selectedFactId === null ? (current.observations[0]?.id ?? null) : selectedFactId, mode === 'view' ? 'view' : 'edit');
                    this.#state = { ...this.#state, editorOpen: true };
                }
            }
        } catch (error) {
            if (host.isCurrent() && this.#openings.isActive(opening)) host.report(ensureError(error));
        } finally {
            if (host.isCurrent() && this.#openings.isActive(opening)) {
                this.#state = { ...this.#state, opening: false };
                this.#scheduleRender();
            }
        }
    }
    #releaseRecord(): void {
        this.#recordEvents?.abort();
        this.#recordEvents = null;
        if (this.#recordContent) {
            this.#openings.invalidate();
            this.#state = { ...this.#state, opening: false };
            this.#recordContent.replaceChildren();
            delete this.#recordContent.dataset['memoryRevision'];
        }
        this.#recordContent = null;
        this.#recordEntry = null;
        this.#scheduleRender();
    }
    #closeRecord(): void {
        if (this.#recordContent) requireModalPresenter().close(CHAT_MEMORY_RECORD_MODAL_ID, { force: true });
        this.#releaseRecord();
    }
    refreshLocalization(): void {
        if (this.#active) this.#scheduleRender();
    }

    #scheduleRender(): void {
        if (this.#renderPending) return;
        this.#renderPending = true;
        const session = this.#session.value;
        this.#resources.requestAnimationFrame(() => {
            this.#renderPending = false;
            if (this.#active && this.#session.isActive(session)) {
                renderMemoryLibrary(this.#host.root, this.#state);
                if (this.#recordContent && this.#recordEntry) {
                    renderMemoryRecordManagement(this.#recordContent, this.#recordEntry, memoryStaleMessage(this.#state));
                    for (const control of dom.resolveAll('button', this.#recordContent)) {
                        if (control instanceof HTMLButtonElement) setControlDisabledState(control, this.#state.pending || this.#state.opening || this.#state.editorOpen);
                    }
                }
            } else if (this.#active) this.#scheduleRender();
        });
    }
}

export { MemoryLibraryController };
export type { MemoryLibraryHost };
