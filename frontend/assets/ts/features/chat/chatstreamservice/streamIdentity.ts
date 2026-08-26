/* SoAI - Chat feature stream identity [frontend/assets/ts/features/chat/chatstreamservice/streamIdentity.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';
import type { ChatStreamEventEnvelope } from '@core/realtime/eventcontracts/chatStreamEnvelope.ts';
import { requireAssistantMessageIdentity } from '@core/chat/assistantIdentity.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

type ChatStreamIdentity = {
    convId: string;
    requestId: string;
    assistantTimestamp: number;
    assistantTurnTimestamp: number;
    modelVariantIndex: number;
};

type ChatStreamIdentityKey = string;

type ChatStreamMessageOrderIdentity = {
    assistantTimestamp: number;
    assistantTurnTimestamp: number;
    modelVariantIndex: number;
};

type ChatStreamIdentitySource = {
    conversationId: string;
    requestId: string;
    assistantTimestamp: number;
    assistantTurnTimestamp: number;
    modelVariantIndex: number;
};

const requireChatStreamIdentityFromStartArguments = (inputArguments: ChatStreamIdentitySource): ChatStreamIdentity => {
    const context = 'Chat stream start';
    const convId = normalizeConversationId(inputArguments.conversationId);
    if (!convId) {
        throw new Error('Chat stream start requires a valid conversationId');
    }
    const requestId = toTrimmedString(inputArguments.requestId);
    if (!requestId) {
        throw new Error('Chat stream start requires a valid requestId');
    }
    const identity = requireAssistantMessageIdentity({
        assistantTimestamp: inputArguments.assistantTimestamp,
        assistantTurnTimestamp: inputArguments.assistantTurnTimestamp,
        modelVariantIndex: inputArguments.modelVariantIndex,
        context
    });
    return {
        convId,
        requestId,
        assistantTimestamp: identity.assistantTimestamp,
        assistantTurnTimestamp: identity.assistantTurnTimestamp,
        modelVariantIndex: identity.modelVariantIndex
    };
};

const requireChatStreamIdentityFromEnvelope = (envelope: ChatStreamEventEnvelope): ChatStreamIdentity => {
    const context = 'Chat stream event';
    const convId = normalizeConversationId(envelope.convId);
    if (!convId) {
        throw new Error('Chat stream event requires a valid conv_id');
    }
    const requestId = envelope.requestId.trim();
    if (!requestId) {
        throw new Error('Chat stream event requires a valid request_id');
    }
    const identity = requireAssistantMessageIdentity({
        assistantTimestamp: envelope.payload.assistantAtMs,
        assistantTurnTimestamp: envelope.payload.assistantTurnAtMs,
        modelVariantIndex: envelope.payload.modelVariantIndex,
        context
    });
    return {
        convId,
        requestId,
        assistantTimestamp: identity.assistantTimestamp,
        assistantTurnTimestamp: identity.assistantTurnTimestamp,
        modelVariantIndex: identity.modelVariantIndex
    };
};

const requireChatStreamIdentityFromSession = (conversationId: string, session: ChatStreamSession): ChatStreamIdentity => {
    const context = 'Chat stream session';
    const convId = normalizeConversationId(conversationId);
    if (!convId) {
        throw new Error('Chat stream session requires a valid conversation id');
    }
    const requestId = toTrimmedString(session.requestId);
    if (!requestId) {
        throw new Error('Chat stream session requires a valid request id');
    }
    const identity = requireAssistantMessageIdentity({
        assistantTimestamp: session.assistantTimestamp,
        assistantTurnTimestamp: session.assistantTurnTimestamp,
        modelVariantIndex: session.modelVariantIndex,
        context
    });
    return {
        convId,
        requestId,
        assistantTimestamp: identity.assistantTimestamp,
        assistantTurnTimestamp: identity.assistantTurnTimestamp,
        modelVariantIndex: identity.modelVariantIndex
    };
};

const buildChatStreamIdentityKey = (identity: ChatStreamIdentity): ChatStreamIdentityKey => {
    return `${identity.convId}|${identity.requestId}|${String(identity.assistantTurnTimestamp)}|${String(identity.modelVariantIndex)}|${String(identity.assistantTimestamp)}`;
};

const compareChatStreamMessageOrderIdentities = (left: ChatStreamMessageOrderIdentity, right: ChatStreamMessageOrderIdentity): number => {
    if (left.assistantTurnTimestamp !== right.assistantTurnTimestamp) {
        return left.assistantTurnTimestamp < right.assistantTurnTimestamp ? -1 : 1;
    }
    if (left.assistantTimestamp !== right.assistantTimestamp) {
        return left.assistantTimestamp < right.assistantTimestamp ? -1 : 1;
    }
    if (left.modelVariantIndex !== right.modelVariantIndex) {
        return left.modelVariantIndex < right.modelVariantIndex ? -1 : 1;
    }
    return 0;
};

const compareChatStreamIdentityToSession = (identity: ChatStreamMessageOrderIdentity, session: ChatStreamSession): number => {
    return compareChatStreamMessageOrderIdentities(identity, session);
};

const chatStreamIdentityPrecedesSession = (identity: ChatStreamMessageOrderIdentity, session: ChatStreamSession): boolean => {
    return compareChatStreamIdentityToSession(identity, session) < 0;
};

const sessionPrecedesChatStreamIdentity = (session: ChatStreamSession, identity: ChatStreamMessageOrderIdentity): boolean => {
    return compareChatStreamIdentityToSession(identity, session) > 0;
};

export { buildChatStreamIdentityKey, chatStreamIdentityPrecedesSession, compareChatStreamIdentityToSession, compareChatStreamMessageOrderIdentities, requireChatStreamIdentityFromEnvelope, requireChatStreamIdentityFromSession, requireChatStreamIdentityFromStartArguments, sessionPrecedesChatStreamIdentity };
export type { ChatStreamIdentity, ChatStreamIdentityKey, ChatStreamMessageOrderIdentity };
