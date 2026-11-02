/* SoAI - PTY terminal session subscriptions [frontend/assets/ts/features/terminal/ptyTerminalSessionSubscriptions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { WEBSOCKET_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/registry.ts';
import type { PtyBusyEvent, PtyConnectedEvent, PtyDisconnectedEvent, PtyErrorEvent, PtyExitedEvent, PtyOutputEvent } from '@core/realtime/eventcontracts/terminalContracts.ts';
import { createWebSocketContractBinding, subscribeManagedWebSocketContracts } from '@core/realtime/websocketBatchSubscription.ts';
import type { WebSocketDispatchContext } from '@core/websocketclient/types.ts';

type SubscriptionOptions = {
    onConnected: (payload: PtyConnectedEvent, context: WebSocketDispatchContext) => void;
    onOutput: (payload: PtyOutputEvent, context: WebSocketDispatchContext) => void;
    onExited: (payload: PtyExitedEvent, context: WebSocketDispatchContext) => void;
    onDisconnected: (payload: PtyDisconnectedEvent, context: WebSocketDispatchContext) => void;
    onError: (payload: PtyErrorEvent, context: WebSocketDispatchContext) => void;
    onBusy: (payload: PtyBusyEvent, context: WebSocketDispatchContext) => void;
    onWebSocketDisconnected: (context: WebSocketDispatchContext) => void;
    onWebSocketConnected: (context: WebSocketDispatchContext) => void;
};

const subscribePtyTerminalSessionEvents = (options: SubscriptionOptions): (() => void) => {
    return subscribeManagedWebSocketContracts({
        label: 'PtyTerminalSession',
        events: [
            createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.terminal.connected, handler: options.onConnected }),
            createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.terminal.output, handler: options.onOutput }),
            createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.terminal.exited, handler: options.onExited }),
            createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.terminal.disconnected, handler: options.onDisconnected }),
            createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.terminal.error, handler: options.onError }),
            createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.terminal.busy, handler: options.onBusy }),
            createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.lifecycle.disconnected, handler: (_payload, context) => options.onWebSocketDisconnected(context) }),
            createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.lifecycle.connected, handler: (_payload, context) => options.onWebSocketConnected(context) })
        ]
    });
};

export { subscribePtyTerminalSessionEvents };
