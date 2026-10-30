/* SoAI - Chat page attach modal drag-open binding controller [frontend/assets/ts/pages/chat/controllers/chatpage/lifecycle/attachModalDragOpenBindingController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ATTACH_MODAL_ID } from '@features/attachmodal/public.ts';

import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { bindFileDragModalAutoOpen } from '@core/ui/fileDragModalAutoOpen.ts';
import { AGENT_PLAN_MODAL_ID, ARCHIVED_CONVERSATIONS_MODAL_ID, CHAT_ATTACHMENT_OVERFLOW_MODAL_ID, CHAT_CONFIGURATION_MODAL_ID, CHAT_MCP_DEFAULT_TOOLS_MODAL_ID, CHAT_MEMORY_PROFILE_MODAL_ID, CHAT_TOOL_CALL_OUTPUT_MODAL_ID, CHAT_VOICE_CALL_MODAL_ID, MESSAGE_INFO_MODAL_ID } from '@features/chat/public.ts';
import type { ChatActionHandlersHost } from '@pages/chat/controllers/actionhandlers/core/contracts.ts';
import type { ChatConversationState } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatConversationToolbarManager } from '@pages/chat/controllers/chatpage/conversations/ChatConversationToolbarManager.ts';

interface ChatAttachModalDragOpenBindingHost {
    conversationState: ChatConversationState;
    conversationToolbarSession: ChatConversationToolbarManager;
    getDomContext(): Element | null;
    requireActionHost(): ChatActionHandlersHost;
}

const BLOCKED_MODAL_IDS = Object.freeze([CHAT_CONFIGURATION_MODAL_ID, CHAT_MCP_DEFAULT_TOOLS_MODAL_ID, CHAT_ATTACHMENT_OVERFLOW_MODAL_ID, AGENT_PLAN_MODAL_ID, ARCHIVED_CONVERSATIONS_MODAL_ID, CHAT_VOICE_CALL_MODAL_ID, CHAT_TOOL_CALL_OUTPUT_MODAL_ID, CHAT_MEMORY_PROFILE_MODAL_ID, MESSAGE_INFO_MODAL_ID]);

const bindChatAttachModalDragOpen = (host: ChatAttachModalDragOpenBindingHost, signal: AbortSignal): void => {
    const root = host.getDomContext();
    if (!(root instanceof HTMLElement)) {
        throw new Error('ChatPage requires a root element before binding attach modal drag-open');
    }
    const attachModalHost = host.requireActionHost();
    bindFileDragModalAutoOpen({
        root,
        signal,
        canOpen: () => {
            if (host.conversationState.currentConversationId === null || host.conversationToolbarSession.isSelectionActive()) {
                return false;
            }
            if (!attachModalHost.attachments.fileUploadEnabled()) {
                return false;
            }
            const presenter = requireModalPresenter();
            return !BLOCKED_MODAL_IDS.some((modalId) => presenter.isOpen(modalId));
        },
        isModalOpen: () => requireModalPresenter().isOpen(ATTACH_MODAL_ID),
        openModal: () => attachModalHost.attachments.openDialog({ initialTab: 'upload' }),
        closeModal: () =>
            attachModalHost.execution.run('chat:attachModalOpen', () => {
                const presenter = requireModalPresenter();
                if (presenter.isOpen(ATTACH_MODAL_ID)) {
                    presenter.close(ATTACH_MODAL_ID, { reason: 'drag-open-ended', restoreFocus: false });
                }
            })
    });
};

export { bindChatAttachModalDragOpen };
