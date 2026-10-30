/* SoAI - Conversation find page-session integration and incremental live work [frontend/assets/ts/pages/chat/controllers/conversationfind/ConversationFindSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isPresenceExiting, prepareEnterWithPresence } from '@core/animations/presence/public.ts';
import { dom } from '@core/dom/dom.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { requireConnectionStatus } from '@core/connectionstatus/public.ts';
import { getComputedStyleStrict } from '@core/environment/public.ts';
import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { captureConversationFindPrefill, readMessagesAreaVisibleInsets, scanConversationFindHistory, type ChatActionId } from '@features/chat/public.ts';
import type { ChatSessionDomainOwners, ChatSessionPageOwners, ChatSessionPlatformOwners } from '@pages/chat/controllers/chatpage/runtime/ChatSessionComposition.ts';
import type { ChatConversationViewController } from '@pages/chat/controllers/chatpage/conversations/ChatConversationViewController.ts';
import type { ChatComparisonTurnNavigationController } from '@pages/chat/widgets/comparisonturn/ChatComparisonTurnNavigationController.ts';
import { ConversationFindSearchController } from '@pages/chat/controllers/conversationfind/ConversationFindSearchController.ts';
import { ConversationFindRevealController, type ConversationFindRevealStatus } from '@pages/chat/controllers/conversationfind/ConversationFindRevealController.ts';
import { ConversationFindTimelineController } from '@pages/chat/controllers/conversationfind/ConversationFindTimelineController.ts';
import { ConversationFindView } from '@pages/chat/controllers/conversationfind/view.ts';
import { bindConversationFindInteractions } from '@pages/chat/controllers/conversationfind/interactionEventsController.ts';
import type { ConversationFindSearchContext } from '@pages/chat/controllers/conversationfind/contracts.ts';

interface ConversationFindSessionDependencies {
    domain: Pick<ChatSessionDomainOwners, 'settings' | 'conversationRuntime' | 'composerSurface' | 'viewState' | 'conversationState' | 'taskScope'>;
    page: Pick<ChatSessionPageOwners, 'pageResources'>;
    platform: Pick<ChatSessionPlatformOwners, 'dom'>;
    conversationView: ChatConversationViewController;
    comparison: ChatComparisonTurnNavigationController;
}

class ConversationFindSession {
    readonly #dependencies: ConversationFindSessionDependencies;
    readonly search: ConversationFindSearchController;
    #view: ConversationFindView | null = null;
    #timeline: ConversationFindTimelineController | null = null;
    #reveal: ConversationFindRevealController | null = null;
    #root: HTMLElement | null = null;
    #signal: AbortSignal | null = null;
    #activationSignal: AbortSignal | null = null;
    readonly #activationInvalidated = (): void => this.close(false);
    #returnFocus: HTMLElement | null = null;
    #opening: { prefill: string | null; focus: HTMLElement | null } | null = null;
    #status: ConversationFindRevealStatus = null;
    #active = false;
    #wasExecuting = false;
    #movementRevision = 0;
    #selectingInitial: number | null = null;
    #exits: (() => void)[] = [];

    constructor(dependencies: ConversationFindSessionDependencies) {
        this.#dependencies = dependencies;
        this.search = new ConversationFindSearchController({
            resources: dependencies.page.pageResources.tracker,
            captureContext: () => this.#context(),
            scan: (query, signal) => {
                const conversation = dependencies.conversationView.current();
                if (!conversation) throw new Error('Conversation find requires a displayed conversation');
                const documentRef = dependencies.platform.dom.getDocument();
                return scanConversationFindHistory(dependencies.domain.conversationRuntime.requireStorage(), { conversationId: conversation.id, query, documentRef, projection: dependencies.domain.conversationRuntime.requireMessages().createSearchTextProjection(documentRef), signal });
            },
            runTask: (operationId, task) => dependencies.domain.taskScope.run(operationId, task),
            onChanged: () => this.#changed(),
            onInvalidated: () => {
                this.#reveal?.cancel();
                this.#timeline?.clear();
            },
            reportFailure: (error) => dependencies.conversationView.reportFailure(error)
        });
    }

    #context(): ConversationFindSearchContext | null {
        const { domain, conversationView } = this.#dependencies;
        const conversation = conversationView.current();
        const signal = this.#signal;
        if (!this.#active || !conversation || !signal || signal.aborted || domain.viewState.conversationRenderCache?.viewState !== 'messages' || domain.viewState.conversationRenderCache.conversationKey !== conversation.id) return null;
        const activation = domain.taskScope.captureConversationActivation();
        return {
            conversationId: conversation.id,
            revision: Math.max(conversation.updatedAt, conversation.history?.version ?? 0),
            presentationKey: JSON.stringify([domain.settings.richTextEnabled(), domain.settings.storage.getCodeRecognitionEnabled(), domain.settings.inlineMultimediaPreviewsEnabled(), this.#dependencies.platform.dom.getDocument().documentElement.lang]),
            executionActive: conversationView.isExecuting(conversation.id),
            signal,
            isCurrent: () => this.#active && domain.taskScope.isConversationActivationCurrent(activation, conversation.id) && conversationView.current() === conversation
        };
    }

    initialize(root: HTMLElement, signal: AbortSignal): void {
        this.#active = true;
        this.#signal = signal;
        this.#root = root;
        if (!this.#view) this.#initializeRuntime(root);
        const view = this.#view;
        if (!view) throw new Error('Conversation find view is not initialized');
        bindConversationFindInteractions(
            {
                root,
                wrapper: view.wrapper,
                input: view.input,
                isOpen: () => this.search.snapshot.open,
                isActive: () => this.#active && root.isConnected && root.closest('[inert]') === null && getComputedStyleStrict(root).visibility !== 'hidden' && getComputedStyleStrict(root).display !== 'none',
                hasModal: () => requireModalPresenter().hasOpenModals(),
                isRenaming: () => this.#dependencies.domain.conversationState.conversationRenameState?.scope === 'header',
                canOpen: () => this.#context() !== null,
                open: (prefill, focus) => this.open(prefill, focus),
                captureOpening: (prefill, focus) => {
                    this.#opening = { prefill, focus };
                },
                close: (restoreFocus) => this.close(restoreFocus),
                queryChanged: () => this.search.replaceQuery(view.input.value),
                enter: (backward) => this.#enter(backward),
                navigate: (delta, wrap) => this.navigate(delta, wrap),
                cancelMovement: () => this.cancelMovement()
            },
            signal
        );
        const onAbort = (): void => this.hide();
        signal.addEventListener('abort', onAbort, { once: true });
    }

    #initializeRuntime(root: HTMLElement): void {
        const { domain, page, conversationView, comparison } = this.#dependencies;
        const timeline = new ConversationFindTimelineController({
            root,
            search: this.search,
            resources: page.pageResources.tracker,
            current: () => conversationView.current(),
            createProjection: () => domain.conversationRuntime.requireMessages().createSearchTextProjection(root.ownerDocument),
            isPendingDeletion: (conversation, messageId) => domain.conversationRuntime.requireMessages().isMessagePendingDeletion(conversation, messageId),
            runTask: (id, task) => domain.taskScope.run(id, task)
        });
        this.#timeline = timeline;
        this.#view = new ConversationFindView(
            root,
            () => this.#runSearch(),
            () => this.search.replaceQuery(''),
            page.pageResources.tracker
        );
        this.#reveal = new ConversationFindRevealController({
            search: this.search,
            concurrency: domain.taskScope.concurrency,
            resources: page.pageResources.tracker,
            comparison,
            mounted: timeline.mounted,
            root: timeline.messages,
            current: () => conversationView.current(),
            hasModal: () => requireModalPresenter().hasOpenModals(),
            isEditing: () => domain.conversationRuntime.requireMessages().isMessageEditing(),
            prepareScroll: () => {
                const release = timeline.highlights.beginMovement();
                domain.composerSurface.requireUi().prepareUserScrollReveal();
                return release;
            },
            load: (id, options) => domain.conversationRuntime.requireStorage().loadConversationMessages(id, options),
            render: (canCommit) => conversationView.renderCurrent({ canCommit, viewportStabilityScope: 'caller' }),
            isWindowRendered: (history) => domain.viewState.conversationRenderCache?.renderedHistory === history,
            refreshMounted: (signal) => timeline.refresh(signal, this.search.snapshot.target?.messageId),
            move: async (range, isCurrent, signal) => {
                const generation = this.search.generation;
                await timeline.highlights.move(range, isCurrent, signal);
                timeline.highlights.scheduleGeometry(() => this.search.isCurrent(generation), true);
            },
            recheckEdges: () => domain.composerSurface.requireUi().requestOlderMessagesIfAtTop(),
            runTask: (id, task) => domain.taskScope.run(id, task),
            onStatus: (status) => {
                this.#status = status;
                this.#view?.render(this.search.snapshot, status);
            },
            reportFailure: (error) => conversationView.reportFailure(error)
        });
        this.#exits.push(conversationView.onRendered(() => this.observePresentation()));
        this.#exits.push(requireConnectionStatus().subscribe((event) => this.search.setConnected(event.connected)));
        this.search.setConnected(requireConnectionStatus().isConnected());
    }

    observePresentation(): void {
        this.#view?.render(this.search.snapshot, this.#status);
        const context = this.#context();
        this.search.pruneQueries(new Set(this.#dependencies.domain.conversationState.conversations.keys()));
        this.search.observeAuthority(this.#wasExecuting && context?.executionActive === false);
        this.#wasExecuting = context?.executionActive ?? false;
        this.#timeline?.scheduleRefresh();
    }

    #changed(): void {
        const snapshot = this.search.snapshot;
        this.#dependencies.domain.viewState.conversationFindOpen = snapshot.open;
        this.#dependencies.domain.composerSurface.optionalUi()?.syncChatChromeVisibility();
        this.#dependencies.conversationView.syncTitle();
        this.#view?.render(snapshot, this.#status);
        if (!snapshot.open || !snapshot.query || snapshot.status === 'too-long') return;
        this.#timeline?.paint();
        const generation = this.search.generation;
        if (snapshot.status === 'ready' && snapshot.target === null && snapshot.index.totalOccurrences > 0 && this.#selectingInitial !== generation) {
            this.#selectingInitial = generation;
            this.#dependencies.domain.taskScope.run('chat:find:initial', async () => {
                try {
                    if (this.#signal) await this.#timeline?.refresh(this.#signal);
                    if (this.search.isCurrent(generation)) await this.#selectInitial(generation);
                } finally {
                    if (this.#selectingInitial === generation) this.#selectingInitial = null;
                }
            });
        }
    }

    #runSearch(retryReveal = false): void {
        if (retryReveal) this.cancelMovement();
        const generation = this.search.generation;
        const revision = ++this.#movementRevision;
        const hadTarget = this.search.snapshot.target !== null;
        this.#dependencies.domain.taskScope.run('chat:find:search', async () => {
            await this.search.search();
            const snapshot = this.search.snapshot;
            if (retryReveal && this.search.isCurrent(generation) && snapshot.status === 'ready' && hadTarget && snapshot.target && revision === this.#movementRevision) this.#reveal?.reveal(snapshot.target);
        });
    }

    async #selectInitial(generation: number): Promise<void> {
        const snapshot = this.search.snapshot;
        const area = this.#root ? dom.resolve('.chat-messages-area', this.#root) : null;
        if (snapshot.target || !this.#timeline || !this.#signal || !(area instanceof HTMLElement)) return;
        const bandTop = measureLayoutBox(area).top + readMessagesAreaVisibleInsets(area).top;
        const selected = await this.#timeline.mounted.initialTarget(snapshot.index, bandTop, this.#signal);
        if (selected && this.search.isCurrent(generation)) {
            this.search.selectTarget(selected);
            this.#reveal?.reveal(selected);
        }
    }

    open(prefill: string | null, focus: HTMLElement | null): void {
        if (this.search.snapshot.open || !this.#view || !this.search.open(prefill)) return;
        this.#activationSignal = this.#dependencies.domain.taskScope.captureConversationActivation().signal;
        this.#activationSignal.addEventListener('abort', this.#activationInvalidated, { once: true });
        this.#returnFocus = focus;
        if (isPresenceExiting(this.#view.wrapper)) prepareEnterWithPresence(this.#view.wrapper, true, true)();
        this.#view.searchBar.setValue(this.search.snapshot.query, false);
        this.#view.input.focus({ preventScroll: true });
        this.#view.input.select();
        if (this.search.snapshot.query) this.#runSearch();
    }

    close(restoreFocus = false): void {
        this.#activationSignal?.removeEventListener('abort', this.#activationInvalidated);
        this.#activationSignal = null;
        const wasOpen = this.search.snapshot.open;
        this.#view?.searchBar.cancelPendingSearch();
        this.search.close();
        if (restoreFocus && wasOpen) {
            const focus = this.#returnFocus;
            const style = focus?.ownerDocument.defaultView?.getComputedStyle(focus);
            if (focus?.matches('.chat-input')) this.#dependencies.domain.composerSurface.requireUi().focusComposerFromUserAction();
            else if (focus?.isConnected && !focus.closest('[inert],[hidden],.u-hidden') && !focus.matches(':disabled') && style?.display !== 'none' && style?.visibility !== 'hidden') focus.focus({ preventScroll: true });
            else this.#dependencies.domain.composerSurface.requireUi().focusComposerFromUserAction();
        }
        this.#returnFocus = null;
    }

    navigate(delta: number, wrap: boolean): void {
        this.#movementRevision += 1;
        const target = this.search.navigate(delta, wrap);
        if (target) this.#reveal?.reveal(target);
    }

    #enter(backward: boolean): void {
        if (this.#view?.searchBar.flushPendingSearch()) return;
        if (this.search.snapshot.status === 'ready' && this.search.snapshot.target) this.navigate(backward ? -1 : 1, true);
        else this.#runSearch();
    }

    action(action: ChatActionId): void {
        if (action === 'chat:find-open') {
            if (this.search.snapshot.open) {
                this.close(true);
                return;
            }
            const captured = this.#opening;
            this.#opening = null;
            this.open(captured?.prefill ?? (this.#root ? captureConversationFindPrefill(this.#root) : null), captured?.focus ?? null);
        } else if (action === 'chat:find-close') this.close(true);
        else if (action === 'chat:find-previous') this.navigate(-1, false);
        else if (action === 'chat:find-next') this.navigate(1, false);
        else if (action === 'chat:find-retry') this.#runSearch(true);
    }

    cancelMovement(): void {
        this.#movementRevision += 1;
        this.#reveal?.cancel();
        this.#timeline?.highlights.stopMovement();
    }
    hide(): void {
        this.#active = false;
        this.close(false);
    }
    dispose(): void {
        this.hide();
        this.search.dispose();
        this.#view?.dispose();
        for (const exit of this.#exits) exit();
        this.#exits = [];
        this.#timeline?.dispose();
        this.#timeline = null;
    }
}

export { ConversationFindSession };
