/* SoAI - Chat stream WebSocket event envelope validation [frontend/assets/ts/core/realtime/eventcontracts/chatStreamEnvelope.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isNonNegativeInteger, isPositiveInteger, isString } from '@core/typeGuards.ts';
import { WEBSOCKET_EVENT_TYPES } from '@core/websocketEvents.ts';
import { resolveAssistantMessageIdentity } from '@core/chat/assistantIdentity.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { decodeAssistantTimelinePayload } from '@core/realtime/eventcontracts/assistantTimelineContracts.ts';
import type { AssistantTimelinePayload } from '@core/realtime/eventcontracts/assistantTimelineTypes.ts';

type ChatStreamEventPayload = AssistantTimelinePayload & { assistantAtMs: number; assistantTurnAtMs: number; assistantRevision: number; modelVariantIndex: number };

const normalizeChatStreamEventPayload = (eventType: string, payload: JsonValue): ChatStreamEventPayload | null => {
    const decoded = decodeAssistantTimelinePayload(eventType, payload);
    if (decoded === null || !isPositiveInteger(decoded.assistantRevision)) return null;
    const assistantIdentity = resolveAssistantMessageIdentity({
        assistantTimestamp: decoded.assistantAtMs,
        assistantTurnTimestamp: decoded.assistantTurnAtMs,
        modelVariantIndex: decoded.modelVariantIndex
    });
    if (assistantIdentity === null) return null;
    return {
        ...decoded,
        assistantAtMs: assistantIdentity.assistantTimestamp,
        assistantTurnAtMs: assistantIdentity.assistantTurnTimestamp,
        assistantRevision: decoded.assistantRevision,
        modelVariantIndex: assistantIdentity.modelVariantIndex
    };
};

type ChatStreamTimelineEvent = {
    sequence: number;
    eventType: string;
    payload: ChatStreamEventPayload;
};

type ChatStreamEventEnvelope = ChatStreamTimelineEvent & { type: string; userId: number; convId: string; requestId: string };

const parseChatStreamEventEnvelope = (value: JsonValue): ChatStreamEventEnvelope | null => {
    if (!isJsonObject(value)) {
        return null;
    }
    if (value['type'] !== WEBSOCKET_EVENT_TYPES.CHAT_STREAM_EVENT) {
        return null;
    }
    const convId = toTrimmedString(value['conv_id']);
    if (!convId) {
        return null;
    }
    const requestId = value['request_id'];
    if (!isString(requestId) || !requestId.trim()) {
        return null;
    }
    const eventType = value['event_type'];
    const userId = value['user_id'];
    const sequence = value['sequence'];
    if (!isPositiveInteger(userId) || !isNonNegativeInteger(sequence) || !isString(eventType) || eventType.trim().length === 0 || eventType !== eventType.trim()) return null;
    const payload = value['payload'];
    if (payload === undefined) return null;
    const normalizedPayload = normalizeChatStreamEventPayload(eventType, payload);
    if (normalizedPayload === null) return null;
    return {
        type: WEBSOCKET_EVENT_TYPES.CHAT_STREAM_EVENT,
        userId,
        convId,
        requestId: requestId.trim(),
        sequence,
        eventType,
        payload: normalizedPayload
    };
};

export type { ChatStreamEventEnvelope, ChatStreamEventPayload, ChatStreamTimelineEvent };
export { normalizeChatStreamEventPayload, parseChatStreamEventEnvelope };
