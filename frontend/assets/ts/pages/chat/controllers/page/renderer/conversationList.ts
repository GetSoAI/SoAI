/* SoAI - Chat page conversation list [frontend/assets/ts/pages/chat/controllers/page/renderer/conversationList.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { EMPTY_UI_HTML } from '@core/security/uiHtml.ts';
import { buildConversationListMarkup, CHAT_ICON_SIZE_XS, CONVERSATION_TITLE_MAX_LENGTH, countLogicalConversationMessages, isProtectedEmptyConversation, resolveConversationDisplayTitleFromConversation, type Conversation, type ConversationListItem, type ConversationListOptions } from '@features/chat/public.ts';
import { formatChatDate } from '@pages/chat/controllers/chatUiBehaviors.ts';
import type { ChatConversationListRenderDependencies } from '@pages/chat/controllers/page/renderer/contracts.ts';

const buildConversationTitleEditorHtml = (host: ChatConversationListRenderDependencies, conversationId: string): string => {
    const renameState = host.conversationState.conversationRenameState;
    if (!renameState || renameState.scope !== 'sidebar' || renameState.conversationId !== conversationId) {
        return '';
    }
    const value = host.pageContext.sanitizer.attribute(renameState.draft);
    const label = host.pageContext.sanitizer.attribute(i18n.t('common.edit'));
    return `<div class="conversation-item-title-editor"><input type="text" class="conversation-item-title-input" data-collection-focus-key="conversation-title-rename" value="${value}" aria-label="${label}" maxlength="${CONVERSATION_TITLE_MAX_LENGTH}"></div>`;
};

interface ConversationListRowPresentation {
    item: ConversationListItem;
    signature: string;
}

const resolveConversationListRow = (host: ChatConversationListRenderDependencies, conversation: Conversation): ConversationListRowPresentation => {
    const resolveLogicalCount = (conversation: Conversation, isChatStreaming: boolean): number => {
        const persistedMessageCount = conversation.messageCount ?? null;
        if (conversation.history || (persistedMessageCount !== null && persistedMessageCount > conversation.messages.length)) {
            return conversation.history?.totalCount ?? persistedMessageCount ?? conversation.messages.length;
        }
        const existing = host.viewState.conversationListMetricsCache.get(conversation.id) ?? null;
        if (existing && existing.updatedAt === conversation.updatedAt && existing.isChatStreaming === isChatStreaming) {
            return existing.logicalCount;
        }
        const logicalCount = countLogicalConversationMessages(conversation, { isCurrentStreaming: isChatStreaming });
        host.viewState.conversationListMetricsCache.set(conversation.id, { updatedAt: conversation.updatedAt, isChatStreaming, logicalCount });
        return logicalCount;
    };
    const sidebarStatus = host.conversationView.resolveSidebarStatus(conversation.id);
    const isChatStreaming = sidebarStatus.isChatStreaming;
    const terminalIndicator = sidebarStatus.terminalStatus;
    const isSelected = host.conversationToolbarSession.isConversationSelected(conversation.id);
    const color = conversation.color === undefined ? null : conversation.color;
    const logicalCount = resolveLogicalCount(conversation, isChatStreaming);
    const isRenaming = host.conversationState.conversationRenameState?.scope === 'sidebar' && host.conversationState.conversationRenameState.conversationId === conversation.id;
    const titleLabel = resolveConversationDisplayTitleFromConversation(conversation, i18n.t('chat.conversation.untitled'));
    const deleteDisabled = isProtectedEmptyConversation(host.conversationState.conversations, conversation.id, i18n.t('chat.conversation.newTitle'));
    const signature = `u:${conversation.updatedAt}|fav:${conversation.isFavorite ? '1' : '0'}|act:${conversation.id === host.conversationState.currentConversationId ? '1' : '0'}|sel:${isSelected ? '1' : '0'}|exec:${sidebarStatus.executionStatus}|attn:${sidebarStatus.attentionStatus}|chatStream:${isChatStreaming ? '1' : '0'}|term:${terminalIndicator ?? ''}|auto:${conversation.isAutomation === true ? '1' : '0'}|msg:${conversation.isMessaging === true ? '1' : '0'}|color:${color ?? ''}|cnt:${logicalCount}|rename:${isRenaming ? '1' : '0'}|deleteDisabled:${deleteDisabled ? '1' : '0'}|title:${titleLabel}`;
    const colorLabel = host.presentation.conversationColorLabel(color);
    const baseItem: ConversationListItem = {
        deleteDisabled,
        id: conversation.id,
        isActive: conversation.id === host.conversationState.currentConversationId,
        titleHtml: host.pageContext.sanitizer.html(titleLabel),
        titleLabel,
        dateLabel: formatChatDate(conversation.updatedAt),
        messageLabel: i18n.t('chat.conversation.messageCount', { count: logicalCount }),
        executionStatus: sidebarStatus.executionStatus,
        attentionStatus: sidebarStatus.attentionStatus,
        terminalIndicator,
        isAutomation: conversation.isAutomation === true,
        isMessaging: conversation.isMessaging === true,
        color,
        colorTitle: colorLabel === null ? undefined : colorLabel,
        isFavorite: Boolean(conversation.isFavorite),
        isSelected
    };
    const item = isRenaming ? { ...baseItem, isRenaming: true, titleEditorHtml: buildConversationTitleEditorHtml(host, conversation.id) } : baseItem;
    return { item, signature };
};

const renderConversationListRow = (host: ChatConversationListRenderDependencies, presentation: ConversationListRowPresentation): string => {
    const markupOptions: Omit<ConversationListOptions, 'items'> = {
        deleteIconHtml: host.presentation.cachedIcon('close', CHAT_ICON_SIZE_XS),
        deleteTitle: i18n.t('chat.conversation.deleteTitle'),
        renameSaveIconHtml: host.presentation.cachedIcon('check', CHAT_ICON_SIZE_XS),
        renameSaveTitle: i18n.t('common.save'),
        renameCancelIconHtml: host.presentation.cachedIcon('close', CHAT_ICON_SIZE_XS),
        renameCancelTitle: i18n.t('common.cancel'),
        colorPickerIconHtml: EMPTY_UI_HTML,
        colorPickerTitle: i18n.t('chat.conversation.colorPickerTitle'),
        automationIconHtml: host.presentation.cachedIcon('clock', { size: 14, strokeWidth: 1.7 }),
        automationTitle: i18n.t('chat.conversation.automation'),
        messagingIconHtml: host.presentation.cachedIcon('send', { size: 14, strokeWidth: 1.7 }),
        messagingTitle: i18n.t('chat.conversation.messaging'),
        sanitizer: host.pageContext.sanitizer
    };
    return buildConversationListMarkup({ ...markupOptions, items: [presentation.item] }).html;
};

export { renderConversationListRow, resolveConversationListRow };
export type { ConversationListRowPresentation };
