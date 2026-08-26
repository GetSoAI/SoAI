/* SoAI - Chat stream payload validation helpers [frontend/assets/ts/features/chat/chatstreamservice/streamPayloadValidation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isNonNegativeInteger } from '@core/typeGuards.ts';
import type { ChatStreamEventEnvelope } from '@core/realtime/eventcontracts/chatStreamEnvelope.ts';
import type { ChatStreamCommandErrorEnvelope } from '@core/realtime/eventcontracts/chatStreamCommandError.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

const isChatStreamNonNegativeInteger = (value: JsonValue | null | undefined): value is number => {
    return isNonNegativeInteger(value);
};

const chatStreamEnvelopeMatchesSession = (envelope: ChatStreamEventEnvelope, session: ChatStreamSession): boolean => {
    return normalizeConversationId(envelope.convId) === normalizeConversationId(session.conversationId) && envelope.requestId.trim() === session.requestId.trim();
};

const chatStreamCommandErrorConversationMatchesSession = (envelope: ChatStreamCommandErrorEnvelope, session: ChatStreamSession): boolean => {
    return normalizeConversationId(envelope.convId) === normalizeConversationId(session.conversationId);
};

const chatStreamCommandErrorRequestMatchesSession = (envelope: ChatStreamCommandErrorEnvelope, session: ChatStreamSession): boolean => {
    return envelope.requestId.trim() === session.requestId.trim();
};

export { chatStreamCommandErrorConversationMatchesSession, chatStreamCommandErrorRequestMatchesSession, chatStreamEnvelopeMatchesSession, isChatStreamNonNegativeInteger };
