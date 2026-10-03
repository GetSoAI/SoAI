/* SoAI - Chat conversation header auto-hide chrome surface [frontend/assets/ts/features/chat/chatuimanager/chatConversationHeaderChromeSurface.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isRtl } from '@core/layout/direction.ts';
import { CSS_CLASSES } from '@core/cssConstants.ts';
import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { CHAT_SELECTORS } from '@features/chat/chatConstants.ts';
import { createChatChromeSurfaceController, type ChatChromeSurfaceController } from '@features/chat/chatuimanager/chatChromeSurfaceController.ts';
import { getElement } from '@features/chat/chatuimanager/dom.ts';
import type { ChatUIManagerContext } from '@features/chat/chatuimanager/types.ts';

const AUTO_HIDDEN_CLASS = 'chat-main-container--conversation-header-auto-hidden';
const CONVERSATION_HEADER_SELECTOR = '.chat-conversation-header';
const OPEN_MENU_SELECTOR = '.page-actions__menu--open';

const resolveConversationHeader = (context: ChatUIManagerContext): HTMLElement | null => {
    const header = context.dependencies.optionalUI(CONVERSATION_HEADER_SELECTOR);
    return header instanceof HTMLElement ? header : null;
};

const isTitleEditorOpen = (context: ChatUIManagerContext, header: HTMLElement): boolean => {
    const titleInput = context.dependencies.optionalUI(CHAT_SELECTORS.CONVERSATION_TITLE_INPUT, header);
    return titleInput !== null && !titleInput.classList.contains(CSS_CLASSES.HIDDEN);
};

const hasKeyboardFocus = (header: HTMLElement, documentRef: Document): boolean => {
    const focused = documentRef.activeElement;
    return focused instanceof Element && header.contains(focused) && focused.matches(':focus-visible');
};

const isNearConversationStart = (context: ChatUIManagerContext, header: HTMLElement): boolean => {
    if (context.dependencies.session.getCurrentConversation()?.history?.hasOlder === true) return false;
    const messagesArea = getElement(context, 'messagesArea');
    return messagesArea !== null && messagesArea.scrollTop < measureLayoutBox(header).height;
};

export const setupChatConversationHeaderChromeSurface = (context: ChatUIManagerContext, isGlobalPinned: () => boolean): ChatChromeSurfaceController => {
    const dependencies = context.dependencies;
    const documentRef = dependencies.dom.getDocument();

    const controller = createChatChromeSurfaceController(context, {
        isGlobalPinned,
        config: {
            revealEdge: 'top',
            resolveElement: () => resolveConversationHeader(context),
            resolveRevealBounds: (header) => {
                const container = header.parentElement;
                if (container === null) return null;
                const headerBounds = measureLayoutBox(header);
                const containerTop = measureLayoutBox(container).top;
                const sidebarToggle = dependencies.optionalUI(CHAT_SELECTORS.SIDEBAR_TOGGLE, header);
                const sidebarBounds = sidebarToggle === null ? null : measureLayoutBox(sidebarToggle);
                const rtl = isRtl(header);
                const left = sidebarBounds === null || rtl ? headerBounds.left : Math.max(headerBounds.left, sidebarBounds.right);
                const right = sidebarBounds === null || !rtl ? headerBounds.right : Math.min(headerBounds.right, sidebarBounds.left);
                return { ...headerBounds, x: left, left, right, width: Math.max(0, right - left), y: containerTop, top: containerTop, bottom: containerTop + headerBounds.height };
            },
            isPinned: (header) => !dependencies.settings.isAutoHideChatHeaderEnabled() || isTitleEditorOpen(context, header) || dependencies.optionalUI(OPEN_MENU_SELECTOR, header) !== null || hasKeyboardFocus(header, documentRef) || isNearConversationStart(context, header),
            isRevealBlocked: () => false,
            isPointerTargetIgnored: (target) => target instanceof Element && (target.closest(`${CONVERSATION_HEADER_SELECTOR} ${CHAT_SELECTORS.SIDEBAR_TOGGLE}`) !== null || target.closest(CHAT_SELECTORS.SIDEBAR) !== null),
            project: (header, visible) => {
                const container = header.parentElement;
                if (container !== null && container.classList.contains(AUTO_HIDDEN_CLASS) === visible) dependencies.toggleClassName(container, AUTO_HIDDEN_CLASS, !visible);
            }
        }
    });

    const header = resolveConversationHeader(context);
    if (header !== null) {
        controller.addDisposer(dependencies.runtime.on(header, 'focusin', () => controller.commit(), { passive: true }));
    }

    return controller;
};
