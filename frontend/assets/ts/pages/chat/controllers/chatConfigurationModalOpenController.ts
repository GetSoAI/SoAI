/* SoAI - Chat configuration modal open lifecycle controller [frontend/assets/ts/pages/chat/controllers/chatConfigurationModalOpenController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { CHAT_CONFIGURATION_MODAL_ID, initializeAvatarPreview, type ChatConfigurationModalBindingsHost } from '@features/chat/public.ts';
import { syncCameraInputActionSupport } from '@pages/chat/controllers/page/dom/cameraController.ts';
import { initializeChatConfigurationTabs, type ChatConfigurationTabsHost } from '@pages/chat/widgets/chatconfigurationtabs/ChatConfigurationTabsController.ts';
import type { ChatUiTaskScopeHost } from '@pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';

const CHAT_CONFIGURATION_OPEN_SEQUENCE = 'configuration-modal-open';

interface ChatConfigurationModalOpenHost extends ChatUiTaskScopeHost, PageDomOwnerHost, PageFeedbackOwnerHost {}

const isChatConfigurationModalOpenCurrent = (host: ChatConfigurationModalOpenHost, modal: HTMLElement, openToken: number): boolean => {
    const presenter = requireModalPresenter();
    return host.taskScope.concurrency.isRenderSequenceCurrent(CHAT_CONFIGURATION_OPEN_SEQUENCE, openToken) && presenter.isOpen(CHAT_CONFIGURATION_MODAL_ID) && presenter.requireElement(CHAT_CONFIGURATION_MODAL_ID) === modal;
};

const beginChatConfigurationModalOpen = (inputArguments: { host: ChatConfigurationModalOpenHost; tabsHost: ChatConfigurationTabsHost; modalBindingsHost: ChatConfigurationModalBindingsHost; modal: HTMLElement; onTabsReady: () => void }): void => {
    const openToken = inputArguments.host.taskScope.concurrency.beginRenderSequence(CHAT_CONFIGURATION_OPEN_SEQUENCE);
    inputArguments.modal.dataset['chatConfigurationOpening'] = 'true';
    inputArguments.tabsHost.resetConfigurationScroll(inputArguments.modal);
    void initializeChatConfigurationTabs(inputArguments.tabsHost, inputArguments.modal)
        .then((): void => {
            if (!isChatConfigurationModalOpenCurrent(inputArguments.host, inputArguments.modal, openToken)) {
                return;
            }
            inputArguments.onTabsReady();
            initializeAvatarPreview(inputArguments.modalBindingsHost, inputArguments.modal);
            syncCameraInputActionSupport(inputArguments.host);
        })
        .catch((error): void => {
            errorHandler.error('ChatPage', 'Failed to initialize chat configuration modal', ensureError(error));
            inputArguments.host.feedback.show(i18n.t('chat.configuration.notifications.loadFailed'), 'error');
        })
        .finally((): void => {
            if (inputArguments.host.taskScope.concurrency.isRenderSequenceCurrent(CHAT_CONFIGURATION_OPEN_SEQUENCE, openToken)) {
                delete inputArguments.modal.dataset['chatConfigurationOpening'];
            }
        });
};

const invalidateChatConfigurationModalOpen = (host: ChatConfigurationModalOpenHost): void => {
    host.taskScope.concurrency.beginRenderSequence(CHAT_CONFIGURATION_OPEN_SEQUENCE);
};

export { beginChatConfigurationModalOpen, invalidateChatConfigurationModalOpen };
