/* SoAI - Chat sidebar bounded conversation presentation [frontend/assets/ts/pages/chat/controllers/page/renderer/ConversationListPresentationController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseConversationId } from '@core/chat/conversationIdentifier.ts';
import { BoundedCollectionRenderer, type BoundedCollectionCommitContext } from '@core/data/boundedcollectionrenderer/public.ts';
import { createHtmlFragment } from '@core/dom/html.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { arraysEqual } from '@core/primitives/equality.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { EMPTY_UI_HTML } from '@core/security/uiHtml.ts';
import { renderEmptyState } from '@core/ui/emptyState.ts';
import { CHAT_SELECTORS } from '@features/chat/public.ts';
import { resolveSidebarConversationOrder } from '@pages/chat/controllers/page/conversationListOrderingController.ts';
import { renderConversationListRow, resolveConversationListRow, type ConversationListRowPresentation } from '@pages/chat/controllers/page/renderer/conversationList.ts';
import { readConversationListScrollState, resolveConversationListScrollAnchor, writeConversationListScrollState, type ConversationListScrollState } from '@pages/chat/controllers/page/renderer/conversationListScrollState.ts';
import type { ChatConversationListRenderDependencies } from '@pages/chat/controllers/page/renderer/contracts.ts';
import type { SidebarListReadiness } from '@pages/chat/controllers/chatpage/conversations/contracts.ts';

interface PendingRender {
    reject(error: Error): void;
    resolve(): void;
}

interface StagedPresentation {
    ids: readonly string[];
    signatures: ReadonlyMap<string, string>;
    consumedStoredScrollState: boolean;
}

const CONVERSATION_LIST_STRIPE_OFFSET_CLASS = 'conversations-list--stripe-offset';

class ConversationListPresentationController {
    readonly #host: ChatConversationListRenderDependencies;
    readonly #renderer: BoundedCollectionRenderer<ConversationListRowPresentation>;
    readonly #pendingRenders = new Set<PendingRender>();
    #committedIds: readonly string[] = [];
    #committedSignatures: ReadonlyMap<string, string> = new Map();
    #criteriaSignature = '';
    #stagedPresentation: StagedPresentation | null = null;
    #committedContainer: HTMLElement | null = null;
    #searchEmptyStateElement: HTMLElement | null = null;
    #activeRender: Promise<void> | null = null;
    #visible = false;
    #pendingWhileHidden = true;
    #visibilityGeneration = 0;
    #invalidated = true;
    #surfaceSuspended = false;
    #disposed = false;
    #storedScrollState: ConversationListScrollState | null;
    #scrollContainer: HTMLElement | null = null;
    readonly #scrollListener = (): void => this.#persistScrollPosition();

    constructor(host: ChatConversationListRenderDependencies) {
        this.#host = host;
        this.#storedScrollState = readConversationListScrollState();
        this.#renderer = new BoundedCollectionRenderer({
            resolveContainer: () => this.#resolveContainer(),
            resolveEmptyState: () => this.#resolveEmptyState(),
            resolveItemIdentifier: (element) => element.dataset['id'] ?? null,
            renderItem: (presentation) => this.#renderRow(presentation),
            loadingLabel: () => i18n.t('chat.conversation.loadingMore'),
            onCommit: (context) => this.#commitPresentation(context),
            onError: (error) => this.#handleFailure(error)
        });
    }

    async render(): Promise<void> {
        if (this.#disposed || !this.#visible) {
            this.#pendingWhileHidden = true;
            return;
        }
        const conversations = resolveSidebarConversationOrder(this.#host);
        const lookup = new Map<string, ConversationListRowPresentation>();
        const signatures = new Map<string, string>();
        for (const conversation of conversations) {
            const presentation = resolveConversationListRow(this.#host, conversation);
            lookup.set(conversation.id, presentation);
            signatures.set(conversation.id, presentation.signature);
        }
        const ids = conversations.map((conversation) => conversation.id);
        const dirtyIds = new Set<string>();
        for (const identifier of ids) {
            if (this.#invalidated || this.#committedSignatures.get(identifier) !== signatures.get(identifier)) dirtyIds.add(identifier);
        }
        const criteriaSignature = `${this.#host.viewState.searchQueryLower}|${parseConversationId(this.#host.viewState.searchQuery) ?? ''}|${this.#host.viewState.showFavoritesAtTop ? '1' : '0'}|${this.#host.settings.parameters.hideAutomationRuns === true ? '1' : '0'}|${this.#host.settings.parameters.hideMessagingConversations === true ? '1' : '0'}`;
        const resetScroll = criteriaSignature !== this.#criteriaSignature;
        const orderChanged = !arraysEqual(ids, this.#committedIds);
        const surfaceChanged = this.#resolveContainer() !== this.#committedContainer;
        this.#pendingWhileHidden = false;
        this.#updateEmptyState(ids.length === 0 && this.#host.viewState.searchQueryLower.length > 0);
        if (!this.#invalidated && !this.#surfaceSuspended && !resetScroll && !orderChanged && !surfaceChanged && dirtyIds.size === 0) return;
        this.#criteriaSignature = criteriaSignature;
        const restoreViewportAnchor = resolveConversationListScrollAnchor(this.#storedScrollState, ids);
        this.#stagedPresentation = { ids, signatures, consumedStoredScrollState: this.#storedScrollState !== null };
        const completion = createDeferred<void>();
        this.#pendingRenders.add(completion);
        this.#activeRender = completion.promise;
        this.#renderer.update({ ids, lookup, dirtyIds: [...dirtyIds], resetScroll, restoreViewportAnchor: restoreViewportAnchor ?? undefined });
        await completion.promise;
    }

    async syncVisibility(visible: boolean): Promise<SidebarListReadiness> {
        if (this.#disposed) return { isCurrent: () => false };
        if (this.#visible !== visible) {
            this.#visible = visible;
            this.#visibilityGeneration += 1;
        }
        const generation = this.#visibilityGeneration;
        if (!visible) {
            this.#persistScrollPosition();
            this.#detachScrollListener();
            this.#pendingWhileHidden = true;
            this.#surfaceSuspended = true;
            this.#renderer.suspendSurface();
            this.#settlePending();
            return { isCurrent: () => false };
        }
        if (this.#pendingWhileHidden) await this.render();
        else if (this.#activeRender !== null) await this.#activeRender;
        return { isCurrent: () => !this.#disposed && this.#visible && generation === this.#visibilityGeneration };
    }

    invalidate(): void {
        this.#invalidated = true;
        this.#pendingWhileHidden = true;
    }

    async revealConversation(conversationId: string): Promise<boolean> {
        await this.render();
        if (this.#disposed || !this.#visible) return false;
        return await this.#renderer.reveal(conversationId);
    }

    dispose(): void {
        if (this.#disposed) return;
        this.#disposed = true;
        this.#persistScrollPosition();
        this.#detachScrollListener();
        this.#renderer.dispose();
        this.#settlePending();
        this.#stagedPresentation = null;
        this.#committedIds = [];
        this.#committedSignatures = new Map();
        this.#committedContainer = null;
        this.#searchEmptyStateElement = null;
        this.#activeRender = null;
    }

    #resolveContainer(): HTMLElement | null {
        const container = this.#host.pageDom.optional(CHAT_SELECTORS.CONVERSATIONS_LIST);
        return container instanceof HTMLElement ? container : null;
    }

    #resolveEmptyState(): HTMLElement | null {
        if (this.#host.viewState.searchQueryLower.length === 0) return null;
        return this.#resolveEmptyStateElement();
    }

    #resolveEmptyStateElement(): HTMLElement | null {
        const emptyState = this.#host.pageDom.optional(CHAT_SELECTORS.CONVERSATIONS_LIST_EMPTY);
        return emptyState instanceof HTMLElement && emptyState !== this.#resolveContainer() ? emptyState : null;
    }

    #renderRow(presentation: ConversationListRowPresentation): HTMLElement {
        const container = this.#resolveContainer();
        if (container === null) throw new Error('Conversation list rendering surface is unavailable');
        const fragment = createHtmlFragment({ documentRef: container.ownerDocument, html: renderConversationListRow(this.#host, presentation), context: container });
        if (fragment.childElementCount !== 1 || !(fragment.firstElementChild instanceof HTMLElement)) throw new Error(`Conversation row markup must contain exactly one element for ${presentation.item.id}`);
        return fragment.firstElementChild;
    }

    #updateEmptyState(showSearchEmptyState: boolean): void {
        const emptyState = this.#resolveEmptyStateElement();
        if (showSearchEmptyState && emptyState !== null) {
            if (emptyState !== this.#searchEmptyStateElement) this.#host.pageDom.updateHtml(emptyState, renderEmptyState({ title: i18n.t('chat.search.noResults'), className: 'ui-empty-state--simple' }), { escape: false });
            this.#searchEmptyStateElement = emptyState;
            return;
        }
        if (this.#searchEmptyStateElement === null) return;
        this.#host.pageDom.updateHtml(this.#searchEmptyStateElement, EMPTY_UI_HTML);
        this.#host.pageDom.toggleClass(this.#searchEmptyStateElement, 'u-hidden', true);
        this.#searchEmptyStateElement = null;
    }

    #commitPresentation(context: BoundedCollectionCommitContext): void {
        const container = context.container;
        this.#committedContainer = container;
        this.#surfaceSuspended = false;
        this.#host.pageDom.toggleClass(container, CONVERSATION_LIST_STRIPE_OFFSET_CLASS, Math.max(0, context.totalCount - context.rangeEnd) % 2 === 1);
        if (this.#stagedPresentation !== null) {
            this.#committedIds = this.#stagedPresentation.ids;
            this.#committedSignatures = this.#stagedPresentation.signatures;
            if (this.#stagedPresentation.consumedStoredScrollState) this.#storedScrollState = null;
            this.#stagedPresentation = null;
            this.#invalidated = false;
        }
        this.#attachScrollListener(container);
        this.#settlePending();
    }

    #attachScrollListener(container: HTMLElement): void {
        if (this.#scrollContainer === container) return;
        this.#detachScrollListener();
        container.addEventListener('scroll', this.#scrollListener, { passive: true });
        this.#scrollContainer = container;
    }

    #detachScrollListener(): void {
        if (this.#scrollContainer === null) return;
        this.#scrollContainer.removeEventListener('scroll', this.#scrollListener);
        this.#scrollContainer = null;
    }

    #persistScrollPosition(): void {
        if (this.#scrollContainer === null || this.#committedIds.length === 0) return;
        writeConversationListScrollState(this.#scrollContainer, this.#committedIds);
    }

    #handleFailure(error: Error): void {
        this.#stagedPresentation = null;
        this.#invalidated = true;
        this.#pendingWhileHidden = true;
        if (this.#pendingRenders.size === 0) errorHandler.error('ConversationListPresentationController', 'Conversation list pagination failed', error);
        for (const pending of this.#pendingRenders) pending.reject(error);
        this.#pendingRenders.clear();
        this.#activeRender = null;
    }

    #settlePending(): void {
        for (const pending of this.#pendingRenders) pending.resolve();
        this.#pendingRenders.clear();
        this.#activeRender = null;
    }
}

export { ConversationListPresentationController };
