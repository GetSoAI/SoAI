/* SoAI - Chat page avatar handlers [frontend/assets/ts/pages/chat/controllers/chatpage/construction/avatarHandlers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { MODAL_PRESENTER_SERVICE_ID, requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { getServiceContainer } from '@core/serviceContainer.ts';
import { CHAT_CONFIGURATION_MODAL_ID } from '@features/chat/public.ts';
import type { ChatConversationViewHost } from '@pages/chat/controllers/chatpage/conversations/contracts.ts';
import type { ChatUiTaskScopeHost } from '@pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';

const AVATAR_PLACEHOLDER_SELECTOR = '.chat-avatar-preview-placeholder';

interface AvatarHandlerHost extends ChatConversationViewHost, ChatUiTaskScopeHost, PageDomOwnerHost, PageFeedbackOwnerHost {}

const optionalConfigurationModal = (): HTMLElement | null => {
    if (!getServiceContainer().has(MODAL_PRESENTER_SERVICE_ID)) {
        return null;
    }
    const presenter = requireModalPresenter();
    if (!presenter.isOpen(CHAT_CONFIGURATION_MODAL_ID)) {
        return null;
    }
    return presenter.requireElement(CHAT_CONFIGURATION_MODAL_ID);
};

const optionalAvatarElement = (host: AvatarHandlerHost, selector: string): HTMLElement | null => {
    const modal = optionalConfigurationModal();
    if (modal) {
        const withinModal = host.pageDom.optionalHTMLElement(selector, modal);
        if (withinModal) {
            return withinModal;
        }
    }
    return host.pageDom.optionalHTMLElement(selector);
};

const triggerAvatarFileInput = (host: AvatarHandlerHost, selector: string): void => {
    const input = optionalAvatarElement(host, selector);
    if (input instanceof HTMLInputElement && input.type === 'file') {
        input.click();
    }
};

const clearAvatarConfigurationPreview = (host: AvatarHandlerHost, previewSelector: string, removeButtonSelector: string): void => {
    const preview = optionalAvatarElement(host, previewSelector);
    if (preview) {
        const existingImage = dom.resolve('.chat-avatar-image', preview);
        if (existingImage) {
            existingImage.remove();
        }
        const placeholder = dom.resolve(AVATAR_PLACEHOLDER_SELECTOR, preview);
        if (placeholder instanceof HTMLElement) {
            placeholder.classList.remove('u-hidden');
        }
    }
    const removeButton = optionalAvatarElement(host, removeButtonSelector);
    if (removeButton) {
        removeButton.classList.add('u-hidden');
    }
};

const handleAvatarRemove = (host: AvatarHandlerHost, storageClear: () => void, previewSelector: string, removeButtonSelector: string, notifyMessage: string): void => {
    storageClear();
    clearAvatarConfigurationPreview(host, previewSelector, removeButtonSelector);
    host.feedback.show(notifyMessage, 'info');
    host.conversationView.invalidate('current');
    host.taskScope.run('chat:avatarRemove', () => host.conversationView.renderCurrent());
};

export { handleAvatarRemove, triggerAvatarFileInput };
