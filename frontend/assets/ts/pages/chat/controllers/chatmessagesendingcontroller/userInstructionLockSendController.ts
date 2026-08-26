/* SoAI - Chat send user instruction lock controller [frontend/assets/ts/pages/chat/controllers/chatmessagesendingcontroller/userInstructionLockSendController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { applyUserSystemPromptToModelSettings, isChatConversationSettingsWritable, readUserSystemPromptLockState, type Conversation } from '@features/chat/public.ts';
import { syncConversationSystemPromptLock } from '@pages/chat/controllers/chatmessagesendingcontroller/effects.ts';
import type { MessageSendingHost } from '@pages/chat/controllers/chatmessagesendingcontroller/types.ts';

const applyLockedUserInstructionForSend = async (host: MessageSendingHost, conversation: Conversation, conversationId: string): Promise<void> => {
    const lockState = readUserSystemPromptLockState(host.services.getChatPreferences());
    if (!lockState.enabled || !isChatConversationSettingsWritable(conversation)) {
        return;
    }
    const applied = applyUserSystemPromptToModelSettings(conversation.modelSettings, lockState.value);
    if (!applied.changed) {
        return;
    }
    const priorModelSettings = conversation.modelSettings;
    conversation.modelSettings = applied.next;
    try {
        await syncConversationSystemPromptLock(host, conversationId, lockState.value);
    } catch (error) {
        conversation.modelSettings = priorModelSettings;
        throw error;
    }
};

export { applyLockedUserInstructionForSend };
