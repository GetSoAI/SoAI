/* SoAI - Chat stream command error contract [frontend/assets/ts/core/realtime/eventcontracts/chatStreamCommandError.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isString } from '@core/typeGuards.ts';
import { WEBSOCKET_EVENT_TYPES } from '@core/websocketEvents.ts';

type ChatStreamCommandErrorEnvelope = JsonObject & {
    type: string;
    convId: string;
    requestId: string;
    phase: string;
    code: string;
    message: string;
};

const parseChatStreamCommandErrorEnvelope = (value: JsonValue): ChatStreamCommandErrorEnvelope | null => {
    if (!isJsonObject(value)) {
        return null;
    }
    if (value['type'] !== WEBSOCKET_EVENT_TYPES.CHAT_STREAM_COMMAND_ERROR) {
        return null;
    }
    if (!isString(value['conv_id']) || !isString(value['request_id']) || !isString(value['phase']) || !isString(value['code']) || !isString(value['message'])) {
        return null;
    }
    return {
        type: WEBSOCKET_EVENT_TYPES.CHAT_STREAM_COMMAND_ERROR,
        convId: value['conv_id'],
        requestId: value['request_id'],
        phase: value['phase'],
        code: value['code'],
        message: value['message']
    };
};

export { parseChatStreamCommandErrorEnvelope };
export type { ChatStreamCommandErrorEnvelope };
