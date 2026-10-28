/* SoAI - Chat configuration shortcut destination ownership [frontend/assets/ts/pages/chat/controllers/chatpage/configuration/ChatConfigurationDestinationController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { playAttentionPulse, type AttentionPulseHandle } from '@core/animations/attentionPulse.ts';
import { dom } from '@core/dom/dom.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { scrollElementToScrollerCenter } from '@core/scroll.ts';
import { CHAT_CONFIGURATION_MODAL_ID, isManagedConfigurationTabHidden, resolveChatConfigurationTabId, type ChatConfigurationTabId } from '@features/chat/public.ts';
import type { TabsComponentContract } from '@pages/chat/widgets/chatconfigurationtabs/ChatConfigurationTabsController.ts';

type ChatConfigurationAttentionTarget = 'context-window';

interface ChatConfigurationDestination {
    tabId: ChatConfigurationTabId;
    attentionTarget?: ChatConfigurationAttentionTarget | undefined;
}

interface ChatConfigurationDestinationControllerOptions {
    pageResources: {
        tracker: {
            requestAnimationFrame(callback: () => void): number;
            cancelAnimationFrame(frameId: number): void;
        };
    };
    isAuthorityLocked(): boolean;
    getTabs(): TabsComponentContract | null;
    setStoredTab(tabId: string): void;
    openModal(): void;
}

interface PendingDestination {
    requestId: number;
    tabId: ChatConfigurationTabId;
    attentionTarget: ChatConfigurationAttentionTarget | null;
}

class ChatConfigurationDestinationController {
    readonly #options: ChatConfigurationDestinationControllerOptions;
    #pending: PendingDestination | null = null;
    #requestSequence = 0;
    #attentionFrame: number | null = null;
    #attentionPulse: AttentionPulseHandle | null = null;
    #applyingTab = false;

    constructor(options: ChatConfigurationDestinationControllerOptions) {
        this.#options = options;
    }

    open(destination: ChatConfigurationDestination): void {
        const requestedTabId = resolveChatConfigurationTabId(destination.tabId);
        const restricted = this.#isRestricted(requestedTabId);
        const tabId = restricted ? 'general' : requestedTabId;
        this.#cancelAttention();
        const pending: PendingDestination = {
            requestId: ++this.#requestSequence,
            tabId,
            attentionTarget: restricted ? null : (destination.attentionTarget ?? null)
        };
        this.#pending = pending;
        const presenter = requireModalPresenter();
        if (!presenter.isOpen(CHAT_CONFIGURATION_MODAL_ID)) {
            this.#options.setStoredTab(tabId);
            this.#options.openModal();
            return;
        }
        const tabs = this.#options.getTabs();
        if (!tabs) {
            this.#options.setStoredTab(tabId);
            return;
        }
        this.#selectVisibleTab(tabs, tabId);
        const modal = presenter.requireElement(CHAT_CONFIGURATION_MODAL_ID);
        if (modal.dataset['chatConfigurationOpening'] !== 'true') this.#applyAttention(pending, modal);
    }

    handleTabsReady(modal: HTMLElement): void {
        const pending = this.#pending;
        if (!pending) return;
        if (this.#isRestricted(pending.tabId)) {
            pending.tabId = 'general';
            pending.attentionTarget = null;
        }
        const tabs = this.#options.getTabs();
        if (!tabs) throw new Error('Chat configuration tabs are unavailable after initialization');
        this.#selectVisibleTab(tabs, pending.tabId);
        this.#applyAttention(pending, modal);
    }

    handleTabChange(tabId: string): void {
        const pending = this.#pending;
        if (!this.#applyingTab && pending && resolveChatConfigurationTabId(tabId) !== pending.tabId) this.cancel();
    }

    cancel(): void {
        this.#requestSequence += 1;
        this.#pending = null;
        this.#cancelAttention();
    }

    dispose(): void {
        this.cancel();
    }

    #selectVisibleTab(tabs: TabsComponentContract, tabId: string): void {
        this.#applyingTab = true;
        try {
            tabs.setActiveTab(tabId);
            this.#options.setStoredTab(tabId);
        } finally {
            this.#applyingTab = false;
        }
    }

    #applyAttention(pending: PendingDestination, modal: HTMLElement): void {
        if (pending.attentionTarget === null) {
            if (this.#pending === pending) this.#pending = null;
            return;
        }
        this.#cancelAttention();
        this.#attentionFrame = this.#options.pageResources.tracker.requestAnimationFrame(() => {
            this.#attentionFrame = null;
            const presenter = requireModalPresenter();
            if (this.#pending !== pending || pending.requestId !== this.#requestSequence || !presenter.isOpen(CHAT_CONFIGURATION_MODAL_ID) || presenter.requireElement(CHAT_CONFIGURATION_MODAL_ID) !== modal) return;
            if (this.#isRestricted(pending.tabId)) {
                const tabs = this.#options.getTabs();
                if (!tabs) throw new Error('Chat configuration tabs are unavailable while applying an authority restriction');
                this.#selectVisibleTab(tabs, 'general');
                this.#pending = null;
                return;
            }
            const target = dom.resolve(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'chat-model-context-window-tokens-group'), modal);
            const scroller = dom.resolve('.chat-configuration-scroll', modal);
            if (!(target instanceof HTMLElement) || !(scroller instanceof HTMLElement)) throw new Error('Chat configuration context-window attention target is unavailable');
            scrollElementToScrollerCenter(scroller, target);
            target.focus({ preventScroll: true });
            this.#attentionPulse = playAttentionPulse(target);
        });
    }

    #isRestricted(tabId: ChatConfigurationTabId): boolean {
        return this.#options.isAuthorityLocked() && isManagedConfigurationTabHidden(tabId);
    }

    #cancelAttention(): void {
        if (this.#attentionFrame !== null) this.#options.pageResources.tracker.cancelAnimationFrame(this.#attentionFrame);
        this.#attentionFrame = null;
        this.#attentionPulse?.cancel();
        this.#attentionPulse = null;
    }
}

export { ChatConfigurationDestinationController };
export type { ChatConfigurationAttentionTarget, ChatConfigurationDestination, ChatConfigurationDestinationControllerOptions };
