/* SoAI - Automation feature realtime subscriptions [frontend/assets/ts/features/automation/runactivity/realtimeSubscriptions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { createWebSocketContractBinding, subscribeManagedWebSocketContracts } from '@core/realtime/websocketBatchSubscription.ts';
import { WEBSOCKET_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/registry.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';

interface AutomationRunActivityRealtimeSubscriptionsOptions {
    subscriptions: ResourceTracker;
    notifyAutomationChanged: () => void;
    notifyRunChanged: (runId: string) => void;
    scheduleRefreshForRun: (runId: string) => void;
}

const bindAutomationRunActivityRealtimeSubscriptions = (options: AutomationRunActivityRealtimeSubscriptionsOptions): void => {
    options.subscriptions.cleanup();
    try {
        options.subscriptions.track(
            subscribeManagedWebSocketContracts({
                label: 'AutomationRunActivity',
                events: [
                    createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.automation.created, handler: options.notifyAutomationChanged }),
                    createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.automation.updated, handler: options.notifyAutomationChanged }),
                    createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.automation.deleted, handler: options.notifyAutomationChanged }),
                    createWebSocketContractBinding({
                        contract: WEBSOCKET_EVENT_CONTRACTS.automation.runCreated,
                        handler: (event): void => {
                            options.scheduleRefreshForRun(event.runId);
                            options.notifyRunChanged(event.runId);
                        }
                    }),
                    createWebSocketContractBinding({
                        contract: WEBSOCKET_EVENT_CONTRACTS.automation.runUpdated,
                        handler: (event): void => {
                            options.scheduleRefreshForRun(event.runId);
                            options.notifyRunChanged(event.runId);
                        }
                    })
                ]
            })
        );
    } catch (subscriptionError) {
        options.subscriptions.cleanup();
        throw ensureError(subscriptionError);
    }
};

export { bindAutomationRunActivityRealtimeSubscriptions };
