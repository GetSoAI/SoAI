/* SoAI - Chat feature conversation list markup [frontend/assets/ts/features/chat/chattemplates/conversationListMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { isArray, isString } from '@core/typeGuards.ts';
import { EMPTY_UI_HTML } from '@core/security/uiHtml.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import type { ConversationListOptions } from '@features/chat/chattemplates/types.ts';

const buildConversationListMarkup = ({ items, deleteIconHtml, deleteTitle, renameSaveIconHtml, renameSaveTitle, renameCancelIconHtml, renameCancelTitle, colorPickerIconHtml, colorPickerTitle, automationIconHtml, automationTitle, messagingIconHtml, messagingTitle, sanitizer }: ConversationListOptions): TrustedHtml => {
    if (!isArray(items) || items.length === 0) {
        return EMPTY_UI_HTML;
    }
    const attr = (value: string): string => sanitizer.attribute(value);
    const delTitleValue = isString(deleteTitle) ? deleteTitle : '';
    const renameSaveLabelValue = isString(renameSaveTitle) ? renameSaveTitle : '';
    const renameSaveLabel = attr(renameSaveLabelValue);
    const renameCancelLabelValue = isString(renameCancelTitle) ? renameCancelTitle : '';
    const renameCancelLabel = attr(renameCancelLabelValue);
    const defaultColorTitle = isString(colorPickerTitle) ? colorPickerTitle : '';
    const defaultAutomationTitle = isString(automationTitle) ? automationTitle : '';
    const resolvedAutomationIcon = automationIconHtml ?? EMPTY_UI_HTML;
    const defaultMessagingTitle = isString(messagingTitle) ? messagingTitle : '';
    const resolvedMessagingIcon = messagingIconHtml ?? EMPTY_UI_HTML;
    const markup = items
        .map((item) => {
            const activeClass = item.isActive ? ' is-active' : '';
            const selectedClass = item.isSelected ? ' is-selected' : '';
            const renamingClass = item.isRenaming ? ' is-renaming' : '';
            const safeId = attr(item.id);
            const safeColor = item.color ? attr(item.color) : '';
            const colorAttr = safeColor ? ` data-conversation-color="${safeColor}"` : '';
            const favoriteAttr = item.isFavorite ? ' data-is-favorite="true"' : '';
            const executionStatus = item.executionStatus && item.executionStatus !== 'idle' ? item.executionStatus : '';
            const executionAttr = executionStatus ? ` data-conversation-execution-status="${attr(executionStatus)}"` : '';
            const attentionStatus = item.attentionStatus && item.attentionStatus !== 'none' ? item.attentionStatus : '';
            const attentionAttr = attentionStatus ? ` data-conversation-attention-status="${attr(attentionStatus)}"` : '';
            const terminalIndicatorAttr = item.terminalIndicator ? ` data-terminal-indicator="${attr(item.terminalIndicator)}"` : '';
            const automationAttr = item.isAutomation ? ' data-is-automation="true"' : '';
            const automationIndicator = item.isAutomation ? `<span class="conversation-automation-indicator" data-tooltip="${attr(defaultAutomationTitle)}" aria-label="${attr(defaultAutomationTitle)}">${renderIconSlot(resolvedAutomationIcon)}</span>` : '';
            const messagingAttr = item.isMessaging ? ' data-is-messaging="true"' : '';
            const messagingIndicator = item.isMessaging ? `<span class="conversation-messaging-indicator" data-tooltip="${attr(defaultMessagingTitle)}" aria-label="${attr(defaultMessagingTitle)}">${renderIconSlot(resolvedMessagingIcon)}</span>` : '';
            const favoriteIndicator = item.isFavorite ? '<span class="conversation-favorite-indicator" aria-hidden="true">★</span>' : '';
            const favoritePickerClass = item.isFavorite ? ' conversation-favorite-color-picker' : '';
            const itemColorTitleValue = isString(item.colorTitle) ? item.colorTitle : defaultColorTitle;
            const itemColorTitle = attr(itemColorTitleValue);
            const itemDeleteTitleValue = isString(item.deleteTitle) ? item.deleteTitle : delTitleValue;
            const itemDeleteTitle = attr(itemDeleteTitleValue);
            const itemTitleLabel = attr(item.titleLabel);

            const titleMarkup = item.isRenaming ? item.titleEditorHtml : `<div class="conversation-item-title">${item.titleHtml}</div>`;
            const informationContent = `${titleMarkup}<div class="conversation-meta"><span class="conversation-date">${item.dateLabel}</span><span class="conversation-messages">${item.messageLabel}</span>${automationIndicator}${messagingIndicator}${favoriteIndicator}</div>`;
            const informationMarkup = item.isRenaming ? `<div class="conversation-info">${informationContent}</div>` : `<button type="button" class="conversation-info" data-action="chat:switch-conversation" aria-label="${itemTitleLabel}" data-tooltip="${itemTitleLabel}">${informationContent}</button>`;

            const deleteButtonMarkup = item.deleteDisabled ? '<span class="conversation-action-btn conversation-action-btn--spacer" aria-hidden="true"></span>' : `<button type="button" class="conversation-action-btn delete-conversation message-action ui-icon-button ui-icon-button-small" data-action="chat:delete-conversation" aria-label="${itemDeleteTitle}" data-tooltip="${itemDeleteTitle}">${renderIconSlot(deleteIconHtml)}</button>`;
            const defaultActionsMarkup = `${deleteButtonMarkup}<button type="button" class="conversation-action-btn color-picker-trigger message-action ui-icon-button ui-icon-button-small${favoritePickerClass}" data-action="chat:open-conversation-color-picker" aria-label="${itemColorTitle}" data-tooltip="${itemColorTitle}">${renderIconSlot(colorPickerIconHtml)}</button>`;

            const actionsMarkup = item.isRenaming ? `<button type="button" class="conversation-action-btn rename-cancel-conversation message-action ui-icon-button ui-icon-button-small ui-variant-neutral" data-action="chat:conversation-list-title-cancel" aria-label="${renameCancelLabel}" data-tooltip="${renameCancelLabel}">${renderIconSlot(renameCancelIconHtml)}</button><button type="button" class="conversation-action-btn rename-save-conversation message-action ui-icon-button ui-icon-button-small ui-variant-accent" data-action="chat:conversation-list-title-save" aria-label="${renameSaveLabel}" data-tooltip="${renameSaveLabel}">${renderIconSlot(renameSaveIconHtml)}</button>` : defaultActionsMarkup;
            return `<div class="conversation-item${activeClass}${selectedClass}${renamingClass}" data-id="${safeId}"${colorAttr}${favoriteAttr}${executionAttr}${attentionAttr}${terminalIndicatorAttr}${automationAttr}${messagingAttr}>${informationMarkup}<div class="conversation-item-actions">${actionsMarkup}</div></div>`;
        })
        .join('');
    return toTrustedUiHtml(markup);
};

export { buildConversationListMarkup };
