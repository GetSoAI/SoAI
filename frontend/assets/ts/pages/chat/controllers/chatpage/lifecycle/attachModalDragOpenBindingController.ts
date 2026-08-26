/* SoAI - Chat page attach modal drag-open binding controller [frontend/assets/ts/pages/chat/controllers/chatpage/lifecycle/attachModalDragOpenBindingController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { CHAT_ATTACH_MODAL_ID } from '@features/chat/public.ts';
import { bindChatAttachModalDragOpenController } from '@pages/chat/controllers/chatpage/lifecycle/attachModalDragOpenController.ts';
import type { ChatActionHandlersHost } from '@pages/chat/controllers/actionhandlers/core/contracts.ts';
import type { ChatConversationState } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatConversationToolbarManager } from '@pages/chat/controllers/chatpage/conversations/ChatConversationToolbarManager.ts';
import { openChatAttachModal } from '@pages/chat/controllers/modals/chatattach/chatAttachModal.ts';

interface ChatAttachModalDragOpenBindingHost {
    conversationState: ChatConversationState;
    conversationToolbarSession: ChatConversationToolbarManager;
    getDomContext(): Element | null;
    requireActionHost(): ChatActionHandlersHost;
}

const bindChatAttachModalDragOpen = (host: ChatAttachModalDragOpenBindingHost, signal: AbortSignal): void => {
    const root = host.getDomContext();
    if (!(root instanceof HTMLElement)) {
        throw new Error('ChatPage requires a root element before binding attach modal drag-open');
    }
    const attachModalHost = host.requireActionHost();
    bindChatAttachModalDragOpenController(
        {
            root,
            conversationState: host.conversationState,
            isConversationSelectionActive: () => host.conversationToolbarSession.isSelectionActive(),
            isFileUploadEnabled: () => attachModalHost.attachments.fileUploadEnabled(),
            closeAutoOpenedModal: () =>
                attachModalHost.execution.run('chat:attachModalOpen', () => {
                    const presenter = requireModalPresenter();
                    if (presenter.isOpen(CHAT_ATTACH_MODAL_ID)) {
                        presenter.close(CHAT_ATTACH_MODAL_ID, { reason: 'drag-open-ended', restoreFocus: false });
                    }
                }),
            openUploadTab: () => openChatAttachModal(attachModalHost, { initialTab: 'upload' })
        },
        signal
    );
};

export { bindChatAttachModalDragOpen };
