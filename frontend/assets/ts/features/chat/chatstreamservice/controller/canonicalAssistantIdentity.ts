/* SoAI - Canonical assistant identity resolution [frontend/assets/ts/features/chat/chatstreamservice/controller/canonicalAssistantIdentity.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { resolveAssistantVariantIdentity, type AssistantVariantIdentity } from '@core/chat/assistantIdentity.ts';
import { resolveAssistantTimelineProgress } from '@features/chat/chatstreamservice/assistantStreamMessageState.ts';
import type { StreamUpdate } from '@features/chat/chatstreamservice/controller/types.ts';
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

const isObsoleteStreamingUpdate = (conversation: Conversation | undefined, update: StreamUpdate): boolean => {
    if (update.status !== 'streaming' || conversation === undefined) return false;
    let incomingIdentityInitialized = false;
    let incomingIdentity: AssistantVariantIdentity | null = null;
    const currentAssistant = conversation.messages.find((message) => {
        if (message.role !== 'assistant') return false;
        const currentIdentity = resolveAssistantVariantIdentity({
            assistantTurnTimestamp: message.assistantTurnAtMs,
            modelVariantIndex: message.modelVariantIndex
        });
        if (currentIdentity === null) return false;
        if (!incomingIdentityInitialized) {
            incomingIdentity = resolveAssistantVariantIdentity({
                assistantTurnTimestamp: update.message.assistantTurnAtMs,
                modelVariantIndex: update.message.modelVariantIndex
            });
            incomingIdentityInitialized = true;
        }
        return incomingIdentity !== null && currentIdentity.assistantTurnTimestamp === incomingIdentity.assistantTurnTimestamp && currentIdentity.modelVariantIndex === incomingIdentity.modelVariantIndex;
    });
    return currentAssistant !== undefined && resolveAssistantTimelineProgress(currentAssistant).assistantRevision > update.assistantRevision;
};

export { findCanonicalAssistantMessage, isObsoleteStreamingUpdate };
