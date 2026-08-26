/* SoAI - Frontend typed WebSocket event contract definitions [frontend/assets/ts/core/realtime/eventcontracts/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';

interface WebSocketEventContractIdentity {
    readonly eventType: string;
}

interface WebSocketEventContract<Payload> extends WebSocketEventContractIdentity {
    readonly eventType: string;
    readonly decode: (payload: JsonValue) => Payload;
}

const defineWebSocketEventContract = <Payload>(eventType: string, decode: (payload: JsonValue) => Payload): Readonly<WebSocketEventContract<Payload>> => Object.freeze({ eventType, decode });

export { defineWebSocketEventContract };
export type { WebSocketEventContract, WebSocketEventContractIdentity };
