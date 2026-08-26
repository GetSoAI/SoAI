/* SoAI - Shared frontend WebSocket client session closure [frontend/assets/ts/core/websocketclient/sessionClosure.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';

const WEBSOCKET_AUTHENTICATION_CLOSE_CODE = 4001;
const WEBSOCKET_SESSION_ROTATED_REASON = 'session_rotated';

type WebSocketSessionClosure = 'invalidate' | 'none' | 'rotate';

const readWebSocketSessionClosure = (value: JsonValue | undefined): WebSocketSessionClosure => {
    if (value === 'invalidate' || value === 'rotate' || value === 'none') return value;
    return 'none';
};

const resolveWebSocketSessionClosure = (code: JsonValue | undefined, reason: JsonValue | undefined): WebSocketSessionClosure => {
    if (code !== WEBSOCKET_AUTHENTICATION_CLOSE_CODE) {
        return 'none';
    }
    return reason === WEBSOCKET_SESSION_ROTATED_REASON ? 'rotate' : 'invalidate';
};

export { readWebSocketSessionClosure, resolveWebSocketSessionClosure };
export type { WebSocketSessionClosure };
