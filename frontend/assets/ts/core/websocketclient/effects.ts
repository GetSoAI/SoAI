/* SoAI - Shared frontend WebSocket client effects [frontend/assets/ts/core/websocketclient/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getWebSocketProtocol } from '@core/realtime/transportSecurity.ts';
import { errorHandler } from '@core/errorHandler.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { ENDPOINT, HEARTBEAT_TIMEOUT_MS, RECONNECT_DELAY_INITIAL_MS, RECONNECT_DELAY_MAX_MS, TIMER_KEYS } from '@core/websocketclient/constants.ts';
import { type ConnectionStateInterface, type TimerState } from '@core/websocketclient/types.ts';
import { ensureError } from '@core/errors/coerce.ts';

type WebSocketLevel = 'debug' | 'warn' | 'error';
type WebSocketSeverity = 'info' | 'warn' | 'error';

type ConnectionStateLogger = (level: WebSocketLevel, message: string) => void;
type ConnectionEventEmitter = (stage: string, data?: JsonObject, severity?: WebSocketSeverity) => void;

const clearTimers = (timers: TimerState): void => {
    for (const key of TIMER_KEYS) {
        const timer = timers[key];
        if (timer !== null) {
            clearTimeout(timer);
            timers[key] = null;
        }
    }
};

const buildWebSocketUrl = (connectionState: Pick<ConnectionStateInterface, 'getBaseUrl'>): string | null => {
    const baseUrl = connectionState.getBaseUrl();
    if (!baseUrl) return null;
    let url: URL;
    try {
        url = new URL(baseUrl);
        url.protocol = getWebSocketProtocol(url.protocol);
    } catch (error) {
        errorHandler.warn('WebSocketClient', 'Invalid API base URL for WebSocket connection', ensureError(error));
        return null;
    }
    const normalizedPath = url.pathname.replace(/\/+$/, '');
    url.pathname = normalizedPath + ENDPOINT;
    return url.toString();
};

const calculateReconnectDelay = (reconnectAttempts: number): number => {
    const baseDelay = Math.min(RECONNECT_DELAY_INITIAL_MS * Math.pow(2, reconnectAttempts), RECONNECT_DELAY_MAX_MS);
    const maxJitter = Math.min(250, Math.floor(baseDelay * 0.1));
    const jitter = maxJitter > 0 ? Math.floor(Math.random() * (maxJitter + 1)) : 0;
    return Math.min(baseDelay + jitter, RECONNECT_DELAY_MAX_MS);
};

const startHeartbeatTimer = (options: { timers: TimerState; log: ConnectionStateLogger; emit: ConnectionEventEmitter; closeConnection: () => void; reconnect: () => void }): void => {
    if (options.timers.heartbeat !== null) {
        clearTimeout(options.timers.heartbeat);
    }

    options.timers.heartbeat = setTimeout(() => {
        options.log('warn', 'Heartbeat timeout - server may be unresponsive');
        options.emit('heartbeat:timeout', {}, 'warn');
        options.closeConnection();
        options.reconnect();
    }, HEARTBEAT_TIMEOUT_MS);
};

export { buildWebSocketUrl, calculateReconnectDelay, clearTimers, startHeartbeatTimer };
