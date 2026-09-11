/* SoAI - Chat page UI behaviors [frontend/assets/ts/pages/chat/controllers/chatUiBehaviors.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import type { ChatUiStorage } from '@core/chat/protocols.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { applyMcpToolsToggleButtonState, CHAT_SELECTORS, isAgentModeRequiringTools, type Conversation } from '@features/chat/public.ts';
import { resolveConversationAuthorityLock } from '@core/chat/conversationAuthorityLock.ts';
import { CHAT_COMPOSER_ACTIONS_COLLAPSE_BREAKPOINT_PX, CHAT_DESKTOP_BREAKPOINT_PX, CHAT_SIDEBAR_TOGGLE_REPOSITION_BREAKPOINT_PX } from '@pages/chat/contracts/constants.ts';
import { setupAutoSave, type ChatAutoSavePersistencePort, type TimerHost } from '@pages/chat/controllers/chatAutoSaveController.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { SidebarListReadiness } from '@pages/chat/controllers/chatpage/conversations/contracts.ts';

const CHAT_INPUT_ACTIONS_COLLAPSED_CLASS = 'is-collapsed-into-header';
const CHAT_HEADER_OVERFLOW_COMPOSER_ACTIONS_CLASS = 'has-composer-actions';
const CHAT_REPOSITIONABLE_HEADER_ACTION_SELECTORS: readonly string[] = ['.header-favorite-btn:not(.chat-mobile-auxiliary-action)', '.tools-toggle-btn:not(.chat-mobile-auxiliary-action)', '.plan-bar-toggle-btn'];

interface UiBehaviorPresentationPort extends PageDomOwnerHost {
    getCachedIcon(name: IconName, options?: IconOptions): TrustedHtml;
    updatePageActionsMenuState(): void;
    getViewportWidth(): number;
    isMobileSidebarViewport(): boolean;
}

interface UiBehaviorPersistencePort extends ChatAutoSavePersistencePort {
    getStorage: () => ChatUiStorage;
}

interface UiBehaviorConversationPort {
    getSidebarOpen(): boolean;
    setSidebarOpen(open: boolean): void;
    getShowFavoritesAtTop(): boolean;
    setShowFavoritesAtTop(show: boolean): void;
    getCurrentConversationId(): string | null;
    getConversationById(conversationId: string): Conversation | null;
    isConversationExecuting(conversationId: string): boolean;
    syncSidebarListVisibility(visible: boolean): Promise<SidebarListReadiness>;

    refreshConversationsUI(): void;
    toggleConversationFavoriteById(conversationId: string): void;

    getParameters: () => { widescreenMode?: boolean };
}

interface UiBehaviorLayoutPort {
    applySidebarState(): Promise<void>;
}

interface UiBehaviorHost {
    presentation: UiBehaviorPresentationPort;
    persistence: UiBehaviorPersistencePort;
    conversations: UiBehaviorConversationPort;
    layout: UiBehaviorLayoutPort;
}

type UiBehaviorSource = Omit<UiBehaviorHost, 'layout'>;
interface HeaderActionHost {
    presentation: Pick<UiBehaviorPresentationPort, 'pageDom' | 'getCachedIcon'>;
    conversations: Pick<UiBehaviorConversationPort, 'getCurrentConversationId' | 'getConversationById' | 'isConversationExecuting'>;
}

const createChatUiBehaviorsHost = (source: UiBehaviorSource): UiBehaviorHost => {
    const host: UiBehaviorHost = {
        ...source,
        layout: { applySidebarState: () => applySidebarState(host) }
    };
    return host;
};

const formatChatDate = (timestamp: number): string => {
    const diffMins = (serverEpochMs() - timestamp) / 60000;
    if (diffMins < 1) return i18n.t('chat.time.justNow');
    if (diffMins < 60) return i18n.t('chat.time.minutesAgo', { minutes: Math.floor(diffMins) });
    const diffHours = diffMins / 60;
    if (diffHours < 24) return i18n.t('chat.time.hoursAgo', { hours: Math.floor(diffHours) });
    const diffDays = diffHours / 24;
    if (diffDays < 7) return i18n.t('chat.time.daysAgo', { days: Math.floor(diffDays) });
    return i18n.formatDate(new Date(timestamp), { year: 'numeric', month: 'short', day: 'numeric' });
};

const commitSidebarState = (host: UiBehaviorHost, sidebar: Element, open: boolean): void => {
    host.presentation.pageDom.toggleClass(sidebar, 'is-open', open);
    host.presentation.pageDom.toggleClass(sidebar, 'is-preparing', false);
    const mobileSidebarViewport = host.presentation.isMobileSidebarViewport();
    host.presentation.pageDom.toggleClass(sidebar, 'mobile-open', open && mobileSidebarViewport);
    const toggleBtn = host.presentation.pageDom.optional(CHAT_SELECTORS.SIDEBAR_TOGGLE);
    if (toggleBtn) {
        host.presentation.pageDom.updateHtml(toggleBtn, host.presentation.getCachedIcon(open ? 'panel-left-visible' : 'panel-hidden', { size: 16, strokeWidth: 1.5 }));
        repositionSidebarToggleButton(host, toggleBtn);
    }
    host.presentation.updatePageActionsMenuState();
    syncChatHeaderActionLayout(host);
};

const applySidebarState = async (host: UiBehaviorHost): Promise<void> => {
    const sidebar = host.presentation.pageDom.optional(CHAT_SELECTORS.SIDEBAR);
    if (!sidebar) return;
    const open = host.conversations.getSidebarOpen();
    if (!open) {
        commitSidebarState(host, sidebar, false);
        try {
            await host.conversations.syncSidebarListVisibility(false);
        } catch (error) {
            errorHandler.warn('ChatPage', 'Failed to suspend the hidden conversation list', ensureError(error));
        }
        return;
    }
    if (sidebar.classList.contains('is-open') && !sidebar.classList.contains('is-preparing')) {
        commitSidebarState(host, sidebar, true);
        try {
            await host.conversations.syncSidebarListVisibility(true);
        } catch (error) {
            errorHandler.warn('ChatPage', 'Failed to refresh the visible conversation list', ensureError(error));
        }
        return;
    }
    if (!sidebar.classList.contains('is-open')) {
        host.presentation.pageDom.toggleClass(sidebar, 'is-preparing', true);
    }
    try {
        const readiness = await host.conversations.syncSidebarListVisibility(true);
        if (!readiness.isCurrent() || !host.conversations.getSidebarOpen() || host.presentation.pageDom.optional(CHAT_SELECTORS.SIDEBAR) !== sidebar) return;
        commitSidebarState(host, sidebar, true);
    } catch (error) {
        host.presentation.pageDom.toggleClass(sidebar, 'is-preparing', false);
        host.presentation.pageDom.toggleClass(sidebar, 'is-open', false);
        errorHandler.warn('ChatPage', 'Failed to prepare the conversation list before opening the sidebar', ensureError(error));
    }
};

const repositionSidebarToggleButton = (host: UiBehaviorHost, toggleBtn: Element): void => {
    const isNarrowViewport = host.presentation.getViewportWidth() <= CHAT_SIDEBAR_TOGGLE_REPOSITION_BREAKPOINT_PX;
    const sidebarHeader = host.presentation.pageDom.optional('.chat-sidebar-header');
    const headerLeft = host.presentation.pageDom.optional('.chat-header-left');
    if (!sidebarHeader || !headerLeft) {
        return;
    }
    if (isNarrowViewport && host.conversations.getSidebarOpen()) {
        if (toggleBtn.parentElement !== sidebarHeader) {
            sidebarHeader.insertBefore(toggleBtn, sidebarHeader.firstChild);
        }
    } else if (toggleBtn.parentElement !== headerLeft) {
        headerLeft.insertBefore(toggleBtn, headerLeft.firstChild);
    }
};

const resolveChatHeaderOverflowWrapper = (host: UiBehaviorHost): HTMLElement | null => {
    const overflowWrapper = host.presentation.pageDom.optional('.chat-header-overflow.page-actions');
    return overflowWrapper instanceof HTMLElement ? overflowWrapper : null;
};

const isChatHeaderActionsCollapsed = (host: UiBehaviorHost): boolean => {
    const overflowWrapper = resolveChatHeaderOverflowWrapper(host);
    return overflowWrapper?.classList.contains('page-actions--dropdown') === true;
};

const syncChatComposerCollapseState = (host: UiBehaviorHost): void => {
    const shouldCollapseIntoHeader = host.presentation.getViewportWidth() <= CHAT_COMPOSER_ACTIONS_COLLAPSE_BREAKPOINT_PX;
    const inputActions = host.presentation.pageDom.optional('.chat-input-actions');
    if (inputActions instanceof HTMLElement) {
        host.presentation.pageDom.toggleClass(inputActions, CHAT_INPUT_ACTIONS_COLLAPSED_CLASS, shouldCollapseIntoHeader);
    }
    const overflowWrapper = resolveChatHeaderOverflowWrapper(host);
    if (overflowWrapper instanceof HTMLElement) {
        host.presentation.pageDom.toggleClass(overflowWrapper, CHAT_HEADER_OVERFLOW_COMPOSER_ACTIONS_CLASS, shouldCollapseIntoHeader);
    }
};

const repositionChatHeaderActionToggles = (host: UiBehaviorHost): void => {
    const toggles: HTMLElement[] = [];
    for (const selector of CHAT_REPOSITIONABLE_HEADER_ACTION_SELECTORS) {
        const candidate = host.presentation.pageDom.optional(selector);
        if (candidate instanceof HTMLElement) toggles.push(candidate);
    }
    if (toggles.length === 0) return;

    const headerActions = host.presentation.pageDom.optional('.chat-header-actions');
    if (!(headerActions instanceof HTMLElement)) return;
    const overflowMenu = host.presentation.pageDom.optional('.chat-header-overflow .page-actions__menu');
    if (!(overflowMenu instanceof HTMLElement)) return;

    const collapsed = isChatHeaderActionsCollapsed(host);
    const container = collapsed ? overflowMenu : headerActions;
    const anchorCandidate = host.presentation.pageDom.optional(collapsed ? '.configuration-toggle-btn--dropdown' : '.configuration-toggle-btn:not(.configuration-toggle-btn--dropdown)', container);
    const anchor = anchorCandidate instanceof HTMLElement ? anchorCandidate : null;

    for (const toggle of toggles) {
        if (toggle.parentElement === container) continue;
        if (anchor) {
            container.insertBefore(toggle, anchor);
        } else {
            container.appendChild(toggle);
        }
    }
};

const syncChatHeaderActionLayout = (host: UiBehaviorHost): void => {
    syncChatComposerCollapseState(host);
    repositionChatHeaderActionToggles(host);
};

const toggleFavoritesAtTop = (host: UiBehaviorHost): void => {
    const nextValue = !host.conversations.getShowFavoritesAtTop();
    host.conversations.setShowFavoritesAtTop(nextValue);
    host.persistence.getStorage().setChatShowFavoritesAtTop(nextValue);
    const btn = host.presentation.pageDom.optional('.favorite-toggle-btn');
    if (btn) {
        host.presentation.pageDom.toggleClass(btn, 'is-active', nextValue);
        host.presentation.pageDom.updateHtml(btn, host.presentation.getCachedIcon('star', { size: 16, strokeWidth: 1.5 }));
    }
    host.conversations.refreshConversationsUI();
    host.persistence.getStorageManager().saveState();
};

const updateHeaderFavoriteButton = (host: HeaderActionHost): void => {
    const conversationId = host.conversations.getCurrentConversationId();
    const conversation = conversationId ? host.conversations.getConversationById(conversationId) : null;
    const isFavorite = conversation ? conversation.isFavorite === true : false;
    for (const btn of host.presentation.pageDom.query('.header-favorite-btn')) {
        host.presentation.pageDom.toggleClass(btn, 'is-active', isFavorite);
        host.presentation.pageDom.updateAttribute(btn, 'aria-pressed', isFavorite ? 'true' : 'false');
        const iconContainer = host.presentation.pageDom.optional('.chat-action-icon', btn);
        if (iconContainer) {
            host.presentation.pageDom.updateHtml(iconContainer, host.presentation.getCachedIcon('star', { size: 16, strokeWidth: 1.5 }));
        } else {
            host.presentation.pageDom.updateHtml(btn, host.presentation.getCachedIcon('star', { size: 16, strokeWidth: 1.5 }));
        }
    }
};

const updateHeaderToolsToggleButton = (host: HeaderActionHost): void => {
    const conversationId = host.conversations.getCurrentConversationId();
    const conversation = conversationId ? host.conversations.getConversationById(conversationId) : null;
    const modelSettings = conversation?.modelSettings;
    const toolsEnabled = modelSettings?.mcp?.toolsEnabled === true;
    const modeRequiresTools = isAgentModeRequiringTools(modelSettings);
    const conversationExecuting = conversationId ? host.conversations.isConversationExecuting(conversationId) : false;
    const authorityLock = resolveConversationAuthorityLock(conversation);
    for (const btn of host.presentation.pageDom.query(CHAT_SELECTORS.TOOLS_TOGGLE_BTN)) {
        applyMcpToolsToggleButtonState(btn, { toolsEnabled, modeRequiresTools, conversationExecuting, authorityLock });
    }
};

const applyWidescreenMode = (host: UiBehaviorHost): void => {
    const messagesArea = host.presentation.pageDom.optional(CHAT_SELECTORS.MESSAGES_AREA);
    if (!messagesArea) {
        return;
    }
    const viewportWidth = host.presentation.getViewportWidth();
    const isViewportForcedWidescreen = Number.isFinite(viewportWidth) ? viewportWidth < CHAT_DESKTOP_BREAKPOINT_PX : false;
    const shouldEnable = isViewportForcedWidescreen ? true : Boolean(host.conversations.getParameters().widescreenMode);
    host.presentation.pageDom.toggleClass(messagesArea, 'widescreen-mode', shouldEnable);
};

export { formatChatDate, setupAutoSave, applySidebarState, createChatUiBehaviorsHost, syncChatHeaderActionLayout, toggleFavoritesAtTop, updateHeaderFavoriteButton, updateHeaderToolsToggleButton, applyWidescreenMode };
export type { UiBehaviorHost, TimerHost };
export interface ChatUiBehaviorsOwner {
    uiBehaviors: UiBehaviorHost;
}
