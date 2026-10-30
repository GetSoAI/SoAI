/* SoAI - Chat memory library lifecycle and reconciliation [frontend/assets/ts/pages/chat/widgets/memorytab/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getAuthManager } from '@core/auth/public.ts';
import { getStreamResources, getStreamSubscriptions } from '@core/realtime/streammanager/public.ts';
import { MEMORY_LIBRARY } from '@core/realtime/streammanager/resources/ids.ts';
import { hasSameResourceAuthority } from '@core/realtime/streammanager/resources/resourceSnapshotProjection.ts';
import type { ResourceReconciliationSnapshot } from '@core/realtime/streammanager/resources/resourceReconciliationTypes.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { getEventHub } from '@core/environment/public.ts';
import { dom } from '@core/dom/dom.ts';
import { bindPageActionDispatcher } from '@core/dom/dataActionBinding.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { bindWindowReactivation } from '@core/dom/windowReactivation.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { isLifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { CONTENT_PREVIEW_MODAL_ID } from '@core/ui/modals/contentpreview/constants.ts';
import { i18n } from '@core/i18n/index.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { requireContentPreviewModalService } from '@core/ui/modals/contentpreview/service.ts';
import type { ManagedMemoryEntry } from '@core/api/contracts/webuiMemoryContracts.ts';
import { CHAT_ACTIONS, CHAT_MEMORY_UPDATED_EVENT, CHAT_MEMORY_RECORD_MODAL_ID, isChatActionId } from '@features/chat/public.ts';
import type { MemoryApi, MemoryLibraryState, MemoryMutationHost } from '@pages/chat/widgets/memorytab/contracts.ts';
import { deleteMemoryRecord, openMemoryTextEditor } from '@pages/chat/widgets/memorytab/memoryMutationDomain.ts';
import { disconnectMemoryPresentation, initializeMemoryPresentation, renderMemoryLibrary } from '@pages/chat/widgets/memorytab/memoryPresentationDomain.ts';
import { createMemoryMutationHost } from '@pages/chat/widgets/memorytab/memoryMutationPresentationDomain.ts';
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
    #unsubscribeLibrary: (() => void) | null = null;
    #failureNotified = false;
    readonly #session = new SequenceToken();
    readonly #openings = new SequenceToken();
    readonly #resources = new ResourceTracker();
    #recordContent: HTMLElement | null = null;
    #recordEntry: ManagedMemoryEntry | null = null;
    #recordEvents: AbortController | null = null;
    #active = false;
    #account: number | null = null;
    #renderPending = false;
    #committedRefreshPending = false;
    #state: MemoryLibraryState = { snapshot: null, phase: 'idle', stale: false, query: '', opening: false, editorOpen: false, pending: false };

    constructor(host: MemoryLibraryHost) {
        this.#host = host;
        initializeMemoryPresentation(host.root);
        const invalidateAccount = (): void => {
            this.#closeRecord();
            if (this.#state.editorOpen) requireModalPresenter().close(CONTENT_PREVIEW_MODAL_ID, { force: true, reason: 'account-changed' });
            this.#unsubscribeLibrary?.();
            this.#unsubscribeLibrary = null;
            this.#session.invalidate();
            this.#account = getAuthManager().getCurrentUser()?.id ?? null;
            this.#state = { ...this.#state, snapshot: null, query: '', stale: false, phase: 'idle', opening: false, editorOpen: false, pending: false };
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
                if (this.#active && this.#unsubscribeLibrary) this.#host.runTask('chat:memoryReactivation', () => this.refresh().then(() => {}));
            })
        );
        this.#resources.addEventListener(getEventHub(), CHAT_MEMORY_UPDATED_EVENT, () => {
            if (this.#active && this.#unsubscribeLibrary) getStreamResources().invalidate(MEMORY_LIBRARY, 'memory-local-change');
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
        this.#failureNotified = false;
        this.#closeRecord();
        this.#active = false;
        this.#session.invalidate();
        this.#openings.invalidate();
        this.#unsubscribeLibrary?.();
        this.#unsubscribeLibrary = null;
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
    activate(): void {
        if (!this.#active || this.#account === null || this.#unsubscribeLibrary) return;
        const session = this.#session.value;
        this.#unsubscribeLibrary = getStreamSubscriptions().subscribeResourceState(
            MEMORY_LIBRARY,
            (snapshot) => {
                if (this.#isCurrent(session)) this.#receiveLibrary(snapshot);
            },
            { ensureStart: false }
        );
        getStreamResources().invalidate(MEMORY_LIBRARY, 'memory-library-opened');
    }
    readonly refresh = async (afterCommit = false): Promise<boolean> => {
        if (!this.#active || this.#account === null) return false;
        const session = this.#session.value;
        const alreadyActive = this.#unsubscribeLibrary !== null;
        this.#committedRefreshPending ||= afterCommit;
        this.activate();
        if (alreadyActive) getStreamResources().invalidate(MEMORY_LIBRARY, 'memory-library-refresh');
        try {
            await getStreamResources().ensureResourceStarted(MEMORY_LIBRARY);
            return this.#isCurrent(session) && getStreamResources().getReconciliationSnapshot(MEMORY_LIBRARY).status === 'ready';
        } catch (error) {
            if (this.#isCurrent(session) && !isAbortError(error) && !isLifecycleCancellationError(error) && !this.#failureNotified) {
                this.#failureNotified = true;
                this.#mutationHost().report(ensureError(error), this.#committedRefreshPending ? i18n.t('chat.memory.library.savedRefreshNeeded') : i18n.t('chat.memory.errors.loadFailed'));
            }
            return false;
        }
    };
    #receiveLibrary(snapshot: ResourceReconciliationSnapshot): void {
        if (snapshot.status === 'ready') {
            const library = getStreamResources().getResource(MEMORY_LIBRARY);
            if (library === null || library !== snapshot.value) return;
            this.#state = { ...this.#state, snapshot: library, phase: 'ready', stale: false };
            this.#failureNotified = false;
            this.#committedRefreshPending = false;
            if (this.#recordEntry) {
                this.#recordEntry = library.entries.find((entry) => entry.entity.id === this.#recordEntry?.entity.id) ?? null;
                if (!this.#recordEntry) this.#closeRecord();
            }
        } else {
            const loading = snapshot.status === 'initializing' || snapshot.status === 'recovering';
            this.#state = { ...this.#state, phase: loading ? 'loading' : 'failed', stale: this.#state.snapshot !== null };
            if (snapshot.status === 'error' && snapshot.error && !this.#failureNotified) {
                this.#failureNotified = true;
                this.#mutationHost().report(snapshot.error, this.#committedRefreshPending ? i18n.t('chat.memory.library.savedRefreshNeeded') : i18n.t('chat.memory.errors.loadFailed'));
            }
        }
        this.#scheduleRender();
    }
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
        return createMemoryMutationHost({
            api: this.#host.api,
            isCurrent: () => this.#isCurrent(session),
            state: () => this.#state,
            update: (state) => {
                this.#state = state;
                this.#scheduleRender();
            },
            committed: () => {
                this.#committedRefreshPending = true;
                this.#failureNotified = false;
            },
            show: (message, type) => this.#host.show(message, type)
        });
    }
    async #openEditor(host: MemoryMutationHost, entry: ManagedMemoryEntry, observationId: string | null, mode: 'view' | 'edit' | 'record' | 'entryEdit', opening: number): Promise<void> {
        if (!host.isCurrent() || !this.#openings.isActive(opening)) return;
        try {
            const authority = getStreamResources().getReconciliationSnapshot(MEMORY_LIBRARY);
            let current = await this.#host.api.read(entry.entity.id);
            if (!host.isCurrent() || !this.#openings.isActive(opening) || requireContentPreviewModalService().isOpen()) return;
            if (!hasSameResourceAuthority(authority, getStreamResources().getReconciliationSnapshot(MEMORY_LIBRARY))) {
                const latest = getStreamResources()
                    .getResource(MEMORY_LIBRARY)
                    ?.entries.find((candidate) => candidate.entity.id === entry.entity.id);
                if (!latest) {
                    this.#host.show(i18n.t('chat.memory.errors.missing'), 'warning');
                    return;
                }
                current = latest;
            }
            const recordMode = mode === 'record' || (mode === 'entryEdit' && current.observations.length > 1);
            const selectedFactId = mode === 'entryEdit' ? (current.observations[0]?.id ?? null) : observationId;
            if (current.revision !== entry.revision) {
                getStreamResources().invalidate(MEMORY_LIBRARY, 'memory-authority-changed');
                this.#state = { ...this.#state, stale: this.#state.snapshot !== null, phase: 'ready' };
            }
            if (!recordMode && selectedFactId !== null && !current.observations.some((fact) => fact.id === selectedFactId)) {
                this.#host.show(i18n.t('chat.memory.errors.missing'), 'warning');
                return;
            }
            if (host.isCurrent() && !requireContentPreviewModalService().isOpen()) {
                if (recordMode) {
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
                    renderMemoryRecordManagement(this.#recordContent, this.#recordEntry);
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
