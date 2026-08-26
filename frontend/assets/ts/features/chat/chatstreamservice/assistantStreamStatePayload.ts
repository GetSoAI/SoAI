/* SoAI - Strict assistant stream-state payload normalization [frontend/assets/ts/features/chat/chatstreamservice/assistantStreamStatePayload.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { isChatMessage } from '@features/chat/message/chatMessageGuards.ts';
import { resolveAssistantMessageIdentity } from '@core/chat/assistantIdentity.ts';

type AssistantStreamStateIdentity = {
    assistantTimestamp: number;
    assistantTurnTimestamp: number;
    modelVariantIndex: number;
};

const normalizeAssistantStreamStatePayload = (payload: ChatMessage | undefined): ChatMessage | null => {
    if (payload === undefined) {
        return null;
    }
    if (payload.role !== 'assistant') {
        throw new Error('Assistant stream-state payload must normalize to an assistant message.');
    }
    if (!isChatMessage(payload)) {
        throw new Error('Assistant stream-state payload failed ChatMessage validation after normalization.');
    }
    return payload;
};

const normalizeAssistantStreamStatePayloadForIdentity = (payload: ChatMessage | undefined, identity: AssistantStreamStateIdentity): ChatMessage | null => {
    const normalizedMessage = normalizeAssistantStreamStatePayload(payload);
    if (normalizedMessage === null) {
        return null;
    }
    const normalizedIdentity = resolveAssistantMessageIdentity({
        assistantTimestamp: normalizedMessage.timestamp,
        assistantTurnTimestamp: normalizedMessage.assistantTurnAtMs,
        modelVariantIndex: normalizedMessage.modelVariantIndex
    });
    if (normalizedIdentity === null) {
        return null;
    }
    if (normalizedIdentity.assistantTimestamp !== identity.assistantTimestamp || normalizedIdentity.assistantTurnTimestamp !== identity.assistantTurnTimestamp || normalizedIdentity.modelVariantIndex !== identity.modelVariantIndex) {
        return null;
    }
    return normalizedMessage;
};

export { normalizeAssistantStreamStatePayload, normalizeAssistantStreamStatePayloadForIdentity };
export type { AssistantStreamStateIdentity };
