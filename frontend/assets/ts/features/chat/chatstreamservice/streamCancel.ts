/* SoAI - Chat stream cancellation requests [frontend/assets/ts/features/chat/chatstreamservice/streamCancel.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { createModuleLogger } from '@core/runtime/runtimeContext.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { WEBSOCKET_MESSAGE_TYPES } from '@core/websocketEvents.ts';
import { sendWebSocketMessage } from '@core/websocketclient/service.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';
import { TimeoutTimer } from '@core/timers/timeoutTimer.ts';

const log = createModuleLogger('ChatStreamService', { defaultLevel: 'warn' });
const CHAT_STREAM_CANCEL_TIMEOUT_MS = 15000;

const postChatStreamCancelByIdentity = async (input: { conversationId: string; requestId: string | null; reason: string; forcePendingSteers: boolean }): Promise<void> => {
    const payload: JsonObject = {
        type: WEBSOCKET_MESSAGE_TYPES.CHAT_STREAM_CANCEL,
        'conv_id': input.conversationId,
        reason: input.reason,
        'force_pending_steers': input.forcePendingSteers
    };
    if (input.requestId) {
        payload['request_id'] = input.requestId;
    }
    const abortController = new AbortController();
    const timeoutTimer = new TimeoutTimer(CHAT_STREAM_CANCEL_TIMEOUT_MS, () => abortController.abort('Chat stream cancellation send timed out'));
    timeoutTimer.start();
    try {
        await sendWebSocketMessage(payload, {
            waitForConnection: true,
            timeoutMs: CHAT_STREAM_CANCEL_TIMEOUT_MS,
            signal: abortController.signal
        });
    } finally {
        timeoutTimer.stop();
    }
};

const postChatStreamCancelForSession = async (session: ChatStreamSession, reason: string, forcePendingSteers: boolean): Promise<void> => {
    await postChatStreamCancelByIdentity({
        conversationId: session.conversationId,
        requestId: session.requestId,
        reason,
        forcePendingSteers
    });
};

const requestChatStreamCancel = (session: ChatStreamSession, reason: string, forcePendingSteers: boolean): void => {
    void postChatStreamCancelForSession(session, reason, forcePendingSteers).catch((error) => {
        const runtimeError = ensureError(error);
        log('warn', 'Chat stream cancel request failed', runtimeError);
    });
};

const requestChatStreamCancelByIdentity = (input: { conversationId: string; requestId: string | null; reason: string; forcePendingSteers: boolean }): void => {
    void postChatStreamCancelByIdentity(input).catch((error) => {
        const runtimeError = ensureError(error);
        log('warn', 'Chat stream cancel request failed', runtimeError);
    });
};

export { CHAT_STREAM_CANCEL_TIMEOUT_MS, requestChatStreamCancel, requestChatStreamCancelByIdentity };
