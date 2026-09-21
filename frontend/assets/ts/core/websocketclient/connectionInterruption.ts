/* SoAI - Shared frontend WebSocket client connection interruption [frontend/assets/ts/core/websocketclient/connectionInterruption.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

class WebSocketReconnectInterruptionError extends Error {
    constructor(reason: string) {
        super(`WebSocket reconnect interrupted an operation: ${reason}`);
        this.name = 'WebSocketReconnectInterruptionError';
    }
}

const isWebSocketReconnectInterruption = (error: Error): boolean => error.name === 'WebSocketReconnectInterruptionError';

export { WebSocketReconnectInterruptionError, isWebSocketReconnectInterruption };
