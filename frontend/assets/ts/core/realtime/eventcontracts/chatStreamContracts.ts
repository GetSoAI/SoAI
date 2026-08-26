/* SoAI - Frontend chat stream WebSocket event contracts [frontend/assets/ts/core/realtime/eventcontracts/chatStreamContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { defineWebSocketEventContract } from '@core/realtime/eventcontracts/contracts.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { WEBSOCKET_EVENT_TYPES } from '@core/websocketEvents.ts';
import { parseChatStreamEventEnvelope } from '@core/realtime/eventcontracts/chatStreamEnvelope.ts';
import { parseChatStreamCommandErrorEnvelope } from '@core/realtime/eventcontracts/chatStreamCommandError.ts';
import { parseChatStreamStatusPreviewEventEnvelope } from '@core/realtime/eventcontracts/chatStreamStatusPreview.ts';

const requireDecoded =
    <Payload>(decode: (payload: JsonValue) => Payload | null, label: string) =>
    (payload: JsonValue): Payload => {
        const decoded = decode(payload);
        if (decoded === null) throw new TypeError(`${label} payload is invalid`);
        return decoded;
    };

const CHAT_STREAM_EVENT_CONTRACTS = Object.freeze({
    timeline: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.CHAT_STREAM_EVENT, requireDecoded(parseChatStreamEventEnvelope, 'Chat stream event')),
    commandError: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.CHAT_STREAM_COMMAND_ERROR, requireDecoded(parseChatStreamCommandErrorEnvelope, 'Chat stream command error')),
    statusPreview: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.CHAT_STREAM_STATUS_PREVIEW, requireDecoded(parseChatStreamStatusPreviewEventEnvelope, 'Chat stream status preview'))
});

export { CHAT_STREAM_EVENT_CONTRACTS };
