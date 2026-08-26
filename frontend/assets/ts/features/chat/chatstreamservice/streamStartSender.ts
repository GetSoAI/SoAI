/* SoAI - Chat stream start WebSocket sender [frontend/assets/ts/features/chat/chatstreamservice/streamStartSender.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { sendWebSocketMessage } from '@core/websocketclient/service.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';

type StreamStartSendOutcome = 'sent';

const sendChatStreamStartPayload = async (inputArguments: { session: ChatStreamSession; startPayload: JsonObject }): Promise<StreamStartSendOutcome> => {
    await sendWebSocketMessage(inputArguments.startPayload, {
        waitForConnection: true,
        signal: inputArguments.session.abortController.signal
    });
    return 'sent';
};

export { sendChatStreamStartPayload };
export type { StreamStartSendOutcome };
