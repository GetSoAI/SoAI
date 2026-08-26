/* SoAI - Shared frontend WebSocket client boundary contracts [frontend/assets/ts/core/websocketclient/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';

interface ConnectionControllerEvents {
    onConnected: (payload: { url: string }) => void;
    onDisconnectedEvent: (payload: JsonObject) => void;
    onClosed: (payload: { reason: string; retrying: boolean }) => void;
    onMessage: (event: MessageEvent) => void;
}

export type { ConnectionControllerEvents };
