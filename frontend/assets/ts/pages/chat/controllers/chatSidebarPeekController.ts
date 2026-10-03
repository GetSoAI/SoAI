/* SoAI - Chat sidebar hover peek controller [frontend/assets/ts/pages/chat/controllers/chatSidebarPeekController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { finishPresenceAnimations } from '@core/animations/presence/public.ts';
import { dom } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { MODAL_ROOT_CLASS } from '@core/modals/guards.ts';
import { SIDEBAR_PEEK_CLOSE_DELAY_MS, SIDEBAR_PEEK_OPEN_DELAY_MS } from '@core/layout/sidebar/hoverPeek.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import { isElementNode } from '@core/typeGuards.ts';
import { CHAT_SELECTORS } from '@features/chat/public.ts';
import type { TimerHost } from '@pages/chat/controllers/chatAutoSaveController.ts';
import type { SidebarListReadiness } from '@pages/chat/controllers/chatpage/conversations/contracts.ts';

const CHAT_SIDEBAR_PEEK_CLASS = 'is-peeking';
const CHAT_SIDEBAR_HEADER_TOGGLE_SELECTOR = '.chat-sidebar-header-toggle-btn';
const CHAT_SIDEBAR_PEEK_TRIGGER_SELECTOR = '.chat-header-left .chat-sidebar-toggle-btn';
const CHAT_SIDEBAR_PEEK_HOLD_SELECTOR = 'input:focus, textarea:focus, .conversation-item.color-picker-open, .chat-model-control-primary.is-open, .chat-model-slot.is-open, .chat-toolbar-batch-actions:not(.u-hidden)';
const CHAT_OPEN_MODAL_SELECTOR = `.${MODAL_ROOT_CLASS}[aria-hidden='false']`;
const CARRIED_HOVER_ATTRIBUTE = 'data-hover-carried';

interface ChatSidebarPeekHost {
    pageDom: PageDom;
    timers: TimerHost;
    getDocument(): Document;
    isSidebarOpen(): boolean;
    isMobileSidebarViewport(): boolean;
    syncSidebarListVisibility(visible: boolean): Promise<SidebarListReadiness>;
}

const setSidebarRevealed = (sidebar: Element, revealed: boolean): void => {
    if (!revealed) finishPresenceAnimations(sidebar);
    sidebar.toggleAttribute('data-presence-suspended', !revealed);
    sidebar.toggleAttribute('inert', !revealed);
};

const syncSidebarHeaderToggle = (pageDom: PageDom, sidebar: Element, visible: boolean): void => {
    const toggle = pageDom.optional(CHAT_SIDEBAR_HEADER_TOGGLE_SELECTOR, sidebar);
    if (toggle && toggle.classList.contains('u-hidden') === visible) pageDom.toggleClass(toggle, 'u-hidden', !visible);
};

const isMousePointerEvent = (event: Event): boolean => !(event instanceof PointerEvent) || event.pointerType === 'mouse';

class ChatSidebarPeekController {
    readonly #host: ChatSidebarPeekHost;
    #openTimer: number | null = null;
    #closeTimer: number | null = null;
    #generation = 0;

    constructor(host: ChatSidebarPeekHost) {
        this.#host = host;
    }

    handlePointerOver = (event: Event): void => {
        const target = event.target;
        const sidebar = this.#sidebar();
        if (!isElementNode(target) || !sidebar || !isMousePointerEvent(event)) return;
        this.#carryHover(sidebar, false);
        if (this.#isPeeking(sidebar)) {
            if (this.#isWithinPeekSurface(sidebar, target)) this.#clearCloseTimer();
            return;
        }
        if (target.closest(CHAT_SIDEBAR_PEEK_TRIGGER_SELECTOR) && this.#canPeek() && this.#openTimer === null) {
            this.#openTimer = this.#host.timers.setTimer(this.#handleOpenTimer, SIDEBAR_PEEK_OPEN_DELAY_MS);
        }
    };

    handlePointerOut = (event: Event): void => {
        const target = event.target;
        const sidebar = this.#sidebar();
        if (!isElementNode(target) || !sidebar || !isMousePointerEvent(event)) return;
        const related = event instanceof MouseEvent && isElementNode(event.relatedTarget) ? event.relatedTarget : null;
        if (!this.#isPeeking(sidebar)) {
            if (target.closest(CHAT_SIDEBAR_PEEK_TRIGGER_SELECTOR) && !related?.closest(CHAT_SIDEBAR_PEEK_TRIGGER_SELECTOR)) {
                this.#clearOpenTimer();
                this.#generation += 1;
            }
            return;
        }
        if (this.#isWithinPeekSurface(sidebar, target) && !(related && this.#isWithinPeekSurface(sidebar, related))) this.#scheduleClose();
    };

    handlePointerDown = (target: Element): void => {
        const sidebar = this.#sidebar();
        if (!sidebar) return;
        this.#carryHover(sidebar, false);
        if (this.#isPeeking(sidebar) && !this.#isWithinPeekSurface(sidebar, target)) this.dismiss();
    };

    handleKeydown = (event: Event): void => {
        const sidebar = this.#sidebar();
        if (!(event instanceof KeyboardEvent) || event.key !== 'Escape' || event.defaultPrevented || !sidebar || !this.#isPeeking(sidebar) || this.#isHeld(sidebar)) return;
        this.dismiss();
    };

    dismiss = (): void => {
        this.#clearOpenTimer();
        this.#clearCloseTimer();
        this.#generation += 1;
        const sidebar = this.#sidebar();
        if (!sidebar || !this.#isPeeking(sidebar)) return;
        this.#carryHover(sidebar, false);
        this.#host.pageDom.toggleClass(sidebar, CHAT_SIDEBAR_PEEK_CLASS, false);
        if (this.#host.isSidebarOpen()) return;
        setSidebarRevealed(sidebar, false);
        this.#host.syncSidebarListVisibility(false).catch((error) => {
            errorHandler.warn('ChatPage', 'Failed to suspend the conversation list after closing the sidebar peek', ensureError(error));
        });
    };

    #handleOpenTimer = (): void => {
        this.#openTimer = null;
        this.#open().catch((error) => {
            errorHandler.warn('ChatPage', 'Failed to open the sidebar peek', ensureError(error));
        });
    };

    #handleCloseTimer = (): void => {
        this.#closeTimer = null;
        const sidebar = this.#sidebar();
        if (!sidebar || !this.#isPeeking(sidebar)) return;
        if (this.#isHeld(sidebar)) {
            this.#scheduleClose();
            return;
        }
        this.dismiss();
    };

    async #open(): Promise<void> {
        const sidebar = this.#sidebar();
        if (!sidebar || this.#isPeeking(sidebar) || !this.#canPeek()) return;
        this.#generation += 1;
        const generation = this.#generation;
        syncSidebarHeaderToggle(this.#host.pageDom, sidebar, true);
        try {
            const readiness = await this.#host.syncSidebarListVisibility(true);
            if (generation !== this.#generation || !readiness.isCurrent() || !this.#canPeek() || this.#sidebar() !== sidebar) return;
        } catch (error) {
            errorHandler.warn('ChatPage', 'Failed to prepare the conversation list before peeking the sidebar', ensureError(error));
            return;
        }
        setSidebarRevealed(sidebar, true);
        this.#carryHover(sidebar, true);
        this.#host.pageDom.toggleClass(sidebar, CHAT_SIDEBAR_PEEK_CLASS, true);
    }

    #carryHover(sidebar: Element, carried: boolean): void {
        this.#host.pageDom.optional(CHAT_SIDEBAR_HEADER_TOGGLE_SELECTOR, sidebar)?.toggleAttribute(CARRIED_HOVER_ATTRIBUTE, carried);
    }

    #scheduleClose(): void {
        this.#clearCloseTimer();
        this.#closeTimer = this.#host.timers.setTimer(this.#handleCloseTimer, SIDEBAR_PEEK_CLOSE_DELAY_MS);
    }

    #clearOpenTimer(): void {
        if (this.#openTimer !== null) this.#host.timers.clearTimer(this.#openTimer);
        this.#openTimer = null;
    }

    #clearCloseTimer(): void {
        if (this.#closeTimer !== null) this.#host.timers.clearTimer(this.#closeTimer);
        this.#closeTimer = null;
    }

    #canPeek(): boolean {
        return !this.#host.isSidebarOpen() && !this.#host.isMobileSidebarViewport();
    }

    #isPeeking(sidebar: Element): boolean {
        return sidebar.classList.contains(CHAT_SIDEBAR_PEEK_CLASS);
    }

    #isWithinPeekSurface(sidebar: Element, target: Element): boolean {
        return sidebar.contains(target) || target.closest(CHAT_SIDEBAR_PEEK_TRIGGER_SELECTOR) !== null;
    }

    #isHeld(sidebar: Element): boolean {
        return dom.resolve(CHAT_SIDEBAR_PEEK_HOLD_SELECTOR, sidebar) !== null || dom.resolve(CHAT_OPEN_MODAL_SELECTOR, this.#host.getDocument()) !== null;
    }

    #sidebar(): Element | null {
        return this.#host.pageDom.optional(CHAT_SELECTORS.SIDEBAR);
    }
}

export { CHAT_SIDEBAR_PEEK_CLASS, ChatSidebarPeekController, setSidebarRevealed, syncSidebarHeaderToggle };
export type { ChatSidebarPeekHost };
