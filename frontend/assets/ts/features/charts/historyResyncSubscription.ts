/* SoAI - Charts feature history resync subscription [frontend/assets/ts/features/charts/historyResyncSubscription.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { HistoryResetEvent } from '@core/realtime/eventcontracts/historyResetContracts.ts';
import { WEBSOCKET_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/registry.ts';
import { createWebSocketContractBinding, subscribeManagedWebSocketContracts } from '@core/realtime/websocketBatchSubscription.ts';

interface HistoryResyncSubscriptionOptions {
    label: string;
    resetType: 'metrics' | 'hardware';
    onReset: (event: HistoryResetEvent) => void;
    onReconnect: () => void;
}

const subscribeHistoryResync = (options: HistoryResyncSubscriptionOptions): (() => void) => {
    return subscribeManagedWebSocketContracts({
        label: options.label,
        events: [createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.historyReset[options.resetType], handler: options.onReset, label: options.label }), createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.lifecycle.connected, handler: () => options.onReconnect(), label: options.label })]
    });
};

export { subscribeHistoryResync };
