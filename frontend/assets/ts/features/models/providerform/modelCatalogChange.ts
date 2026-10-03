/* SoAI - Models feature model catalog change wait [frontend/assets/ts/features/models/providerform/modelCatalogChange.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { signalAborted } from '@core/lifecycle/abortSignals.ts';
import { WEBSOCKET_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/registry.ts';
import { subscribeManagedWebSocketContract } from '@core/realtime/websocketBatchSubscription.ts';
import { createDeferred } from '@core/runtime/deferred.ts';

const waitForModelCatalogChange = (signal: AbortSignal): Promise<void> => {
    const completion = createDeferred<void>();
    let settled = false;
    let unsubscribe: (() => void) | null = null;
    const finish = (): void => {
        if (settled) return;
        settled = true;
        signal.removeEventListener('abort', finish);
        const dispose = unsubscribe;
        unsubscribe = null;
        dispose?.();
        completion.resolve();
    };
    signal.addEventListener('abort', finish, { once: true });
    if (signalAborted(signal)) {
        finish();
        return completion.promise;
    }
    unsubscribe = subscribeManagedWebSocketContract({ label: 'ModelsProviderDiscovery', contract: WEBSOCKET_EVENT_CONTRACTS.model.databaseChanged, handler: finish, signal });
    return completion.promise;
};

export { waitForModelCatalogChange };
