/* SoAI - Assistant render cache update commit helper [frontend/assets/ts/features/chat/message/assistantRenderCacheUpdate.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { ChatComparisonTurnRenderModel } from '@features/chat/comparisonTurnRenderModel.ts';
import { resolveChatMessageRenderCacheSignature } from '@features/chat/message/messageRenderSignature.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';
import { normalizeMessageDomId } from '@features/chat/message/messageDomIds.ts';

type AssistantRenderCacheUpdate = (conversationId: string, messageDomId: string, signature: string) => void;

const commitAssistantRenderCacheUpdate = (inputArguments: { updateConversationRenderCache: AssistantRenderCacheUpdate | undefined; conversationId: string; messageDomId: string; message: ChatMessage; comparisonTurn: ChatComparisonTurnRenderModel | null }): void => {
    const conversationId = normalizeConversationId(inputArguments.conversationId);
    const messageDomId = normalizeMessageDomId(inputArguments.messageDomId);
    if (!conversationId || !messageDomId) {
        return;
    }
    const signature = resolveChatMessageRenderCacheSignature(messageDomId, inputArguments.message, inputArguments.comparisonTurn);
    inputArguments.updateConversationRenderCache?.(conversationId, messageDomId, signature);
};

export { commitAssistantRenderCacheUpdate };
export type { AssistantRenderCacheUpdate };
