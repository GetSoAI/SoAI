/* SoAI - Chat page color picker [frontend/assets/ts/pages/chat/controllers/page/dom/colorPicker.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatIconResolver, ChatPageColorPickerHost } from '@pages/chat/controllers/page/dom/contracts.ts';
import type { ChatViewStateHost } from '@pages/chat/state/ChatViewStateManager.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { ChatColorToolkit } from '@features/chat/public.ts';

type ChatColorPickerStateHost = ChatViewStateHost & PageDomOwnerHost;

const hideConversationColorPicker = (host: ChatColorPickerStateHost): void => {
    if (host.viewState.activeColorPickerElement) {
        const parentItem = host.viewState.activeColorPickerElement.closest('.conversation-item');
        if (parentItem) {
            host.pageDom.removeClass(parentItem, 'color-picker-open');
        }
        host.viewState.activeColorPickerElement.remove();
        host.viewState.activeColorPickerElement = null;
    }
    host.viewState.activeColorPickerConversationId = null;
};

const showConversationColorPicker = (host: ChatPageColorPickerHost, colors: ChatColorToolkit, conversationItem: HTMLElement, conversationId: string, getIcon: ChatIconResolver): void => {
    hideConversationColorPicker(host);
    const targetConversationItem = conversationItem.closest('.conversation-item');
    if (!targetConversationItem) {
        throw new Error('ChatPage requires an active conversation item for color picker');
    }
    const conversation = host.conversationState.conversations.get(conversationId);
    const currentColor = conversation ? conversation.color : null;
    const isFavorite = Boolean(conversation && conversation.isFavorite === true);
    const picker = colors.renderPicker(currentColor, isFavorite, host.isConversationExecuting(conversationId));
    const starIcon = host.pageDom.optionalHTMLElement('.chat-color-option-favorite', picker);
    if (starIcon) {
        host.pageDom.updateHtml(starIcon, getIcon('star', { size: 20, strokeWidth: 1.5 }));
    }
    const archiveIcon = host.pageDom.optionalHTMLElement('.chat-color-option-archive', picker);
    if (archiveIcon) {
        host.pageDom.updateHtml(archiveIcon, getIcon('archive', { size: 20, strokeWidth: 1.5 }));
    }
    const renameIcon = host.pageDom.optionalHTMLElement('.chat-color-option-rename', picker);
    if (renameIcon) {
        host.pageDom.updateHtml(renameIcon, getIcon('edit', { size: 20, strokeWidth: 1.5 }));
    }
    const exportIcon = host.pageDom.optionalHTMLElement('.chat-color-option-export', picker);
    if (exportIcon) {
        host.pageDom.updateHtml(exportIcon, getIcon('download', { size: 20, strokeWidth: 1.5 }));
    }
    const actionsContainer = host.pageDom.optionalHTMLElement('.conversation-item-actions', targetConversationItem);
    if (actionsContainer) {
        actionsContainer.appendChild(picker);
    } else {
        targetConversationItem.appendChild(picker);
    }
    host.viewState.activeColorPickerConversationId = conversationId;
    host.viewState.activeColorPickerElement = picker;
    host.pageDom.addClass(targetConversationItem, 'color-picker-open');
};

export { hideConversationColorPicker, showConversationColorPicker };
