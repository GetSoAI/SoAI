/* SoAI - Conversation input server reconciliation [frontend/assets/ts/features/chat/conversationinputs/conversationInputSync.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatConversationInputsManagerDependencies, ConversationInput } from '@features/chat/conversationinputs/ConversationInputTypes.ts';
import { ConversationInputStateStore } from '@features/chat/conversationinputs/ConversationInputStateStore.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

const syncConversationInputs = async (inputArguments: { conversationId: string; dependencies: ChatConversationInputsManagerDependencies; store: ConversationInputStateStore; signal: AbortSignal }): Promise<ConversationInput[]> => {
    const conversationId = normalizeConversationId(inputArguments.conversationId);
    if (!conversationId) {
        return [];
    }
    const version = inputArguments.store.beginSync(conversationId);
    const response = await inputArguments.dependencies.conversationInputsApi.list(conversationId);
    if (inputArguments.signal.aborted || !inputArguments.store.isSyncCurrent(conversationId, version)) {
        return [];
    }
    inputArguments.store.applySyncResult(conversationId, response.items);
    if (inputArguments.dependencies.getCurrentConversationId() === conversationId) {
        inputArguments.dependencies.updateInputQueuePreview();
    }
    return response.items;
};

export { syncConversationInputs };
