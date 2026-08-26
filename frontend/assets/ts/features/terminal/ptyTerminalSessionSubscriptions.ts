/* SoAI - PTY terminal session subscriptions [frontend/assets/ts/features/terminal/ptyTerminalSessionSubscriptions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { WEBSOCKET_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/registry.ts';
import type { PtyBusyEvent, PtyConnectedEvent, PtyDisconnectedEvent, PtyErrorEvent, PtyExitedEvent, PtyOutputEvent } from '@core/realtime/eventcontracts/terminalContracts.ts';
import { createWebSocketContractBinding, subscribeManagedWebSocketContracts } from '@core/realtime/websocketBatchSubscription.ts';

type SubscriptionOptions = {
    onConnected: (payload: PtyConnectedEvent) => void;
    onOutput: (payload: PtyOutputEvent) => void;
    onExited: (payload: PtyExitedEvent) => void;
    onDisconnected: (payload: PtyDisconnectedEvent) => void;
    onError: (payload: PtyErrorEvent) => void;
    onBusy: (payload: PtyBusyEvent) => void;
    onWebSocketDisconnected: () => void;
    onWebSocketConnected: () => void;
};

const subscribePtyTerminalSessionEvents = (options: SubscriptionOptions): (() => void) => {
    return subscribeManagedWebSocketContracts({
        label: 'PtyTerminalSession',
        events: [createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.terminal.connected, handler: options.onConnected }), createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.terminal.output, handler: options.onOutput }), createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.terminal.exited, handler: options.onExited }), createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.terminal.disconnected, handler: options.onDisconnected }), createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.terminal.error, handler: options.onError }), createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.terminal.busy, handler: options.onBusy }), createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.lifecycle.disconnected, handler: options.onWebSocketDisconnected }), createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.lifecycle.connected, handler: options.onWebSocketConnected })]
    });
};

export { subscribePtyTerminalSessionEvents };
