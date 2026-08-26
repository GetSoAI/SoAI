/* SoAI - Agent plan modal state lifecycle for the chat page [frontend/assets/ts/pages/chat/controllers/chatpageagent/agentPlanModalController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { openAgentPlanModal } from '@pages/chat/controllers/chatpageagent/agentPlanModal.ts';
import type { ChatPageAgentHost } from '@pages/chat/controllers/chatpageagent/contracts.ts';
import type { ChatPageAgentState } from '@pages/chat/controllers/chatpageagent/state.ts';

const openChatPageAgentPlanModal = (host: ChatPageAgentHost, state: ChatPageAgentState, isDisposed: () => boolean): void => {
    if (isDisposed()) {
        return;
    }
    const conversationId = host.conversation.getCurrentConversationId();
    if (!conversationId) {
        return;
    }
    openAgentPlanModal({
        host,
        markdown: state.canonicalPlanMarkdown || '',
        title: state.canonicalPlanTitle,
        todo: state.canonicalTodo,
        explanation: state.canonicalTodoExplanation,
        onModalOpen: () => {
            if (isDisposed()) {
                return;
            }
            state.planModalOpen = true;
            state.planHasUnseenUpdate = false;
        },
        onModalClose: () => {
            if (isDisposed()) {
                return;
            }
            state.planModalOpen = false;
        }
    });
};

export { openChatPageAgentPlanModal };
