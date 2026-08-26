/* SoAI - Canonical assistant identity resolution [frontend/assets/ts/features/chat/chatstreamservice/controller/canonicalAssistantIdentity.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { isChatMessage } from '@features/chat/message/chatMessageGuards.ts';
import type { Conversation } from '@features/chat/storage/storageModels.ts';

const findCanonicalAssistantMessage = (conversation: Conversation | null | undefined, assistantMessage: ChatMessage | null): ChatMessage | null => {
    if (!conversation || assistantMessage === null) {
        return null;
    }
    for (const message of conversation.messages) {
        if (!isChatMessage(message) || message.role !== 'assistant') {
            continue;
        }
        if (message.assistantTurnAtMs === assistantMessage.assistantTurnAtMs && message.modelVariantIndex === assistantMessage.modelVariantIndex) {
            return message;
        }
    }
    return null;
};

export { findCanonicalAssistantMessage };
