/* SoAI - Frontend terminal PTY WebSocket transport messages [frontend/assets/ts/features/terminal/ptyTerminalTransport.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { WEBSOCKET_MESSAGE_TYPES } from '@core/websocketEvents.ts';
import { sendWebSocketMessage } from '@core/websocketclient/service.ts';
import { encodeTerminalInput } from '@features/terminal/ptyTerminalCodec.ts';

const sendPtyConnectMessage = (cols: number, rows: number, shell: string | null, signal?: AbortSignal): Promise<void> => {
    const message = {
        type: WEBSOCKET_MESSAGE_TYPES.PTY_CONNECT,
        cols,
        rows,
        shell
    };
    return signal ? sendWebSocketMessage(message, { signal }) : sendWebSocketMessage(message);
};

const sendPtyDisconnectMessage = (): Promise<void> => {
    return sendWebSocketMessage({
        type: WEBSOCKET_MESSAGE_TYPES.PTY_DISCONNECT
    });
};

const sendPtyInputMessage = (data: string): Promise<void> => {
    return sendWebSocketMessage({
        type: WEBSOCKET_MESSAGE_TYPES.PTY_INPUT,
        data: encodeTerminalInput(data)
    });
};

const sendPtyResizeMessage = (cols: number, rows: number): Promise<void> => {
    return sendWebSocketMessage({
        type: WEBSOCKET_MESSAGE_TYPES.PTY_RESIZE,
        cols,
        rows
    });
};

export { sendPtyConnectMessage, sendPtyDisconnectMessage, sendPtyInputMessage, sendPtyResizeMessage };
