/* SoAI - Chat page current conversation state controller [frontend/assets/ts/pages/chat/controllers/page/renderer/currentConversationStateController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { normalizeColor } from '@core/ui/colorToolkitBase.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { CHAT_SELECTORS, normalizeConversationId, normalizeMessageDomId, requireConversationId, resolveConversationDisplayTitleFromConversation, type Conversation } from '@features/chat/public.ts';
import type { ChatCurrentConversationRenderDependencies, ConversationRenderCache } from '@pages/chat/controllers/page/renderer/contracts.ts';
import { getEmptyStateHTML, initializeEmptyStateNav } from '@pages/chat/controllers/page/renderer/emptyState.ts';
import { getSelectedConversationErrorStateHTML, getSelectedConversationLoadingStateHTML } from '@pages/chat/controllers/page/renderer/selectedConversationState.ts';

type ConversationRenderViewState = ConversationRenderCache['viewState'];

const resolveCurrentConversationKey = (host: ChatCurrentConversationRenderDependencies, conversation: Conversation | null): string => {
    if (conversation) {
        return requireConversationId(conversation.id, 'Conversation');
    }
    const currentConversationId = host.conversationState.currentConversationId;
    if (typeof currentConversationId !== 'string') {
        return '';
    }
    const normalizedConversationId = normalizeConversationId(currentConversationId);
    return normalizedConversationId ? normalizedConversationId : '';
};

const syncConversationTitleIndicator = (host: ChatCurrentConversationRenderDependencies, inputArguments: { titleElement: HTMLElement; selector: string; visible: boolean; iconName: IconName }): void => {
    const indicator = host.pageDom.optional(inputArguments.selector, inputArguments.titleElement);
    if (!(indicator instanceof HTMLElement)) {
        return;
    }
    host.pageDom.toggleClass(indicator, 'u-hidden', !inputArguments.visible);
    if (indicator.childNodes.length === 0) {
        host.pageDom.updateHtml(indicator, host.presentation.cachedIcon(inputArguments.iconName, { size: 14, strokeWidth: 1.7 }), { escape: false });
    }
};

const syncCurrentConversationTitleUi = (host: ChatCurrentConversationRenderDependencies, conversation: Conversation | null): void => {
    const titleElement = host.pageDom.optional(CHAT_SELECTORS.CONVERSATION_TITLE);
    const titleInputElement = host.pageDom.optional(CHAT_SELECTORS.CONVERSATION_TITLE_INPUT);
    const saveButton = host.pageDom.optional('.conversation-title-save-btn');
    const cancelButton = host.pageDom.optional('.conversation-title-cancel-btn');
    const pageHeaderActions = host.pageDom.optional('.page-actions__menu');
    const renameState = host.conversationState.conversationRenameState;
    const isEditing = Boolean(renameState && renameState.scope === 'header' && renameState.conversationId === host.conversationState.currentConversationId);
    const titleValue = conversation ? resolveConversationDisplayTitleFromConversation(conversation, i18n.t('chat.conversation.untitled')) : i18n.t('chat.conversation.newTitle');

    if (titleElement instanceof HTMLElement) {
        titleElement.classList.toggle('u-hidden', isEditing);
        if (!isEditing) {
            const titleText = host.pageDom.optional('.conversation-title-text', titleElement);
            syncConversationTitleIndicator(host, { titleElement, selector: '.conversation-title-automation-indicator', visible: conversation?.isAutomation === true, iconName: 'clock' });
            syncConversationTitleIndicator(host, { titleElement, selector: '.conversation-title-messaging-indicator', visible: conversation?.isMessaging === true && conversation?.isAutomation !== true, iconName: 'send' });
            syncConversationTitleIndicator(host, { titleElement, selector: '.conversation-title-archive-indicator', visible: conversation?.isArchived === true, iconName: 'archive' });
            if (titleText instanceof HTMLElement) {
                host.pageDom.updateText(titleText, titleValue);
            } else {
                host.pageDom.updateText(titleElement, titleValue);
            }
        }
    }
    if (titleInputElement instanceof HTMLInputElement) {
        titleInputElement.classList.toggle('u-hidden', !isEditing);
        titleInputElement.value = isEditing && renameState ? renameState.draft : titleValue;
    }
    if (saveButton instanceof HTMLElement) {
        saveButton.classList.toggle('u-hidden', !isEditing);
    }
    if (cancelButton instanceof HTMLElement) {
        cancelButton.classList.toggle('u-hidden', !isEditing);
    }
    if (pageHeaderActions instanceof HTMLElement) {
        pageHeaderActions.classList.toggle('u-hidden', isEditing);
    }
};

const createConversationRenderCache = (inputArguments: { conversationKey: string; viewState: ConversationRenderViewState }): ConversationRenderCache => {
    return {
        conversationKey: inputArguments.conversationKey,
        viewState: inputArguments.viewState,
        domIdsInOrder: [],
        renderSignatureByDomId: new Map()
    };
};

const getOrCreateConversationRenderCache = (host: ChatCurrentConversationRenderDependencies, inputArguments: { conversationKey: string; viewState: ConversationRenderViewState }): ConversationRenderCache => {
    const existing = host.viewState.conversationRenderCache;
    if (existing && existing.conversationKey === inputArguments.conversationKey && existing.viewState === inputArguments.viewState) {
        return existing;
    }
    const next = createConversationRenderCache(inputArguments);
    host.viewState.conversationRenderCache = next;
    return next;
};

const setConversationRenderCacheSignature = (inputArguments: { cache: ConversationRenderCache; domId: string; signature: string | null }): void => {
    if (inputArguments.signature !== null) {
        inputArguments.cache.renderSignatureByDomId.set(inputArguments.domId, inputArguments.signature);
        return;
    }
    inputArguments.cache.renderSignatureByDomId.delete(inputArguments.domId);
};

const deleteConversationRenderCacheSignature = (cache: ConversationRenderCache, domId: string): void => {
    cache.renderSignatureByDomId.delete(domId);
};

const migrateConversationRenderCacheSignature = (inputArguments: { cache: ConversationRenderCache; previousDomId: string; nextDomId: string }): void => {
    const signature = inputArguments.cache.renderSignatureByDomId.get(inputArguments.previousDomId) ?? null;
    deleteConversationRenderCacheSignature(inputArguments.cache, inputArguments.previousDomId);
    if (signature !== null) {
        inputArguments.cache.renderSignatureByDomId.set(inputArguments.nextDomId, signature);
    }
};

const replaceConversationRenderCacheIndex = (inputArguments: { cache: ConversationRenderCache; domIdsInOrder: string[]; signatures: ReadonlyMap<string, string> }): void => {
    inputArguments.cache.domIdsInOrder = [...inputArguments.domIdsInOrder];
    inputArguments.cache.renderSignatureByDomId.clear();
    for (const [domId, signature] of inputArguments.signatures.entries()) {
        inputArguments.cache.renderSignatureByDomId.set(domId, signature);
    }
};

const updateConversationRenderCacheEntry = (inputArguments: { cache: ConversationRenderCache | null; conversationId: string; messageDomId: string; signature: string }): void => {
    const normalizedConversationId = normalizeConversationId(inputArguments.conversationId);
    const normalizedMessageDomId = normalizeMessageDomId(inputArguments.messageDomId);
    if (!normalizedConversationId || !normalizedMessageDomId || !inputArguments.cache || inputArguments.cache.conversationKey !== normalizedConversationId) {
        return;
    }
    setConversationRenderCacheSignature({
        cache: inputArguments.cache,
        domId: normalizedMessageDomId,
        signature: inputArguments.signature
    });
};

const clearStaleCurrentConversationStatusNodes = (container: Element): boolean => {
    let removed = false;
    for (const child of Array.from(container.children)) {
        if (!(child instanceof HTMLElement)) {
            continue;
        }
        if (!child.classList.contains('chat-page-empty-state')) {
            continue;
        }
        child.remove();
        removed = true;
    }
    return removed;
};

const resolveRenderedCurrentConversationStatus = (container: Element): 'empty' | 'loading' | 'error' | null => {
    if (container.children.length !== 1) {
        return null;
    }
    const child = container.firstElementChild;
    if (!(child instanceof HTMLElement) || !child.classList.contains('chat-page-empty-state')) {
        return null;
    }
    const state = child.getAttribute('data-state');
    if (state === 'loading') {
        return 'loading';
    }
    if (state === 'error') {
        return 'error';
    }
    return 'empty';
};

const renderCurrentConversationStatusState = (host: ChatCurrentConversationRenderDependencies, inputArguments: { container: Element; previousCache: ConversationRenderCache | null; selectedConversationState: 'empty' | 'loading' | 'error'; conversationKey: string }): boolean => {
    const cacheMatches = inputArguments.previousCache !== null && inputArguments.previousCache.conversationKey === inputArguments.conversationKey && inputArguments.previousCache.viewState === inputArguments.selectedConversationState;
    const domMatches = resolveRenderedCurrentConversationStatus(inputArguments.container) === inputArguments.selectedConversationState;
    if (cacheMatches && domMatches) {
        return false;
    }
    if (inputArguments.selectedConversationState === 'loading' && domMatches) {
        host.viewState.conversationRenderCache = createConversationRenderCache({
            conversationKey: inputArguments.conversationKey,
            viewState: inputArguments.selectedConversationState
        });
        return false;
    }

    host.emptyState.dispose();
    host.viewState.conversationRenderCache = createConversationRenderCache({
        conversationKey: inputArguments.conversationKey,
        viewState: inputArguments.selectedConversationState
    });
    host.pageDom.updateHtml(inputArguments.container, inputArguments.selectedConversationState === 'empty' ? getEmptyStateHTML(host) : inputArguments.selectedConversationState === 'loading' ? getSelectedConversationLoadingStateHTML(host) : getSelectedConversationErrorStateHTML(host), { escape: false });
    if (inputArguments.selectedConversationState === 'empty') {
        initializeEmptyStateNav(host, inputArguments.container);
    }
    return true;
};

const finalizeCurrentConversationUi = (
    host: ChatCurrentConversationRenderDependencies,
    inputArguments: {
        container: Element;
        conversation: Conversation | null;
        conversationKey: string;
        contentUpdated: boolean;
        messagesCommitted: boolean;
    }
): void => {
    host.pageDom.setDataAttribute(inputArguments.container, 'currentConversationId', inputArguments.conversationKey);
    syncCurrentConversationColorAttribute(host, inputArguments.container, inputArguments.conversation);
    syncCurrentConversationTitleUi(host, inputArguments.conversation);
    if (inputArguments.conversation && inputArguments.messagesCommitted) {
        host.composerSurface.requireUi().restoreConversationScrollPosition();
    } else if (!inputArguments.conversation) {
        host.composerSurface.requireUi().setupScrollListener();
    }
    if (inputArguments.conversation && inputArguments.contentUpdated && host.composerSurface.requireUi().isAutoScrollEnabled()) {
        host.composerSurface.requireUi().scrollToBottom();
    }
    host.presentation.updateExportButtonVisibility();
};

const syncCurrentConversationColorAttribute = (host: ChatCurrentConversationRenderDependencies, container: Element, conversation: Conversation | null): void => {
    host.pageDom.setDataAttribute(container, 'conversationColor', conversation ? normalizeColor(conversation.color) : null);
};

export { clearStaleCurrentConversationStatusNodes, createConversationRenderCache, deleteConversationRenderCacheSignature, finalizeCurrentConversationUi, getOrCreateConversationRenderCache, migrateConversationRenderCacheSignature, renderCurrentConversationStatusState, replaceConversationRenderCacheIndex, resolveCurrentConversationKey, setConversationRenderCacheSignature, syncCurrentConversationColorAttribute, syncCurrentConversationTitleUi, updateConversationRenderCacheEntry };
