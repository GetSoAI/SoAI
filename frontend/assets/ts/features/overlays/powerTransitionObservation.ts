/* SoAI - Power transition transport observation [frontend/assets/ts/features/overlays/powerTransitionObservation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { WEBSOCKET_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/registry.ts';
import { createWebSocketContractBinding, subscribeManagedWebSocketContracts } from '@core/realtime/websocketBatchSubscription.ts';
import { getWebSocketClient } from '@core/websocketclient/service.ts';

interface PowerTransitionObservation {
    onConnected: () => void;
    onInterrupted: () => void;
}

const observePowerTransition = (observation: PowerTransitionObservation): (() => void) => {
    const websocket = getWebSocketClient();
    return subscribeManagedWebSocketContracts({
        label: 'PowerTransition',
        subscribe: (eventType, handler) => websocket.subscribe(eventType, handler),
        events: [
            createWebSocketContractBinding({
                contract: WEBSOCKET_EVENT_CONTRACTS.lifecycle.disconnected,
                handler: (payload) => {
                    if (payload.sessionClosure !== 'none') return;
                    if (payload.reason === 'maintenance' || payload.reason === 'manual' || payload.reason === 'base-url-change') return;
                    observation.onInterrupted();
                }
            }),
            createWebSocketContractBinding({
                contract: WEBSOCKET_EVENT_CONTRACTS.lifecycle.connected,
                handler: observation.onConnected
            })
        ]
    });
};

export { observePowerTransition };
