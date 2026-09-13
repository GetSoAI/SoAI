/* SoAI - Frontend application lifecycle connection recovery monitor [frontend/assets/ts/app/bootstrap/stages/applifecycle/connectionMonitor.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { MainStateIndicatorApi, MaintenanceCoordinatorApi, RestartOverlayApi } from '@app/bootstrap/stages/applifecycle/types.ts';
import { requireAuthManager } from '@core/auth/runtime.ts';
import type { ConnectionStatus } from '@core/connectionstatus/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isPageTerminating } from '@core/lifecycle/pageTermination.ts';
import { createWebSocketContractBinding, subscribeManagedWebSocketContracts } from '@core/realtime/websocketBatchSubscription.ts';
import { WEBSOCKET_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/registry.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { WEBSOCKET_LIFECYCLE_EVENT_TYPES } from '@core/websocketEvents.ts';
import { getWebSocketClient } from '@core/websocketclient/service.ts';

const CONNECTION_LOST_OPERATION = 'connection-lost';
const CONNECTION_LOST_OVERLAY_DELAY_MS = 5000;
const DISCONNECTED_LIFECYCLE_CONTRACT = Object.freeze({ eventType: WEBSOCKET_LIFECYCLE_EVENT_TYPES.DISCONNECTED, contract: WEBSOCKET_EVENT_CONTRACTS.lifecycle.disconnected });

if (DISCONNECTED_LIFECYCLE_CONTRACT.contract.eventType !== DISCONNECTED_LIFECYCLE_CONTRACT.eventType) throw new Error('Disconnected lifecycle event registry does not match the WebSocket protocol');

interface ConnectionMonitorOptions {
    connectionStatus: ConnectionStatus;
    restartOverlay: RestartOverlayApi;
    mainStateIndicator: MainStateIndicatorApi;
    maintenanceCoordinator: MaintenanceCoordinatorApi;
    recoverFreshInstallSession: () => Promise<boolean>;
}

const monitorLifecycleConnectionStatus = ({ connectionStatus, restartOverlay, mainStateIndicator, maintenanceCoordinator, recoverFreshInstallSession }: ConnectionMonitorOptions): (() => void) => {
    const tracker = new ResourceTracker();
    let lastConnected = Boolean(connectionStatus.isConnected());
    let hasConnectedOnce = lastConnected;
    let connectionLossTimerId: number | null = null;
    let disconnectEpoch = 0;
    let activeRecoveryEpoch: number | null = null;
    let isMonitoring = true;

    const clearConnectionLossTimer = (): void => {
        if (connectionLossTimerId === null) return;
        tracker.clearTimeout(connectionLossTimerId);
        connectionLossTimerId = null;
    };

    const isRecoveryUiBlocked = (): boolean => maintenanceCoordinator.getState().active || restartOverlay.isVisible || restartOverlay.currentType === CONNECTION_LOST_OPERATION;

    const hideConnectionLostOverlay = (): void => {
        if (restartOverlay.currentType === CONNECTION_LOST_OPERATION) restartOverlay.hide();
    };

    const scheduleConnectionLostOverlay = (): void => {
        if (!hasConnectedOnce || lastConnected || connectionLossTimerId !== null || isRecoveryUiBlocked()) return;
        connectionLossTimerId = tracker.setTimeout(() => {
            connectionLossTimerId = null;
            if (!hasConnectedOnce || lastConnected || isRecoveryUiBlocked()) return;
            restartOverlay.show(CONNECTION_LOST_OPERATION);
        }, CONNECTION_LOST_OVERLAY_DELAY_MS);
    };

    const invalidateConnectedRecovery = (): void => {
        disconnectEpoch += 1;
    };

    const markConnected = (): void => {
        const epoch = disconnectEpoch;
        if (activeRecoveryEpoch === epoch) return;
        activeRecoveryEpoch = epoch;
        clearConnectionLossTimer();
        lastConnected = true;
        hasConnectedOnce = true;
        mainStateIndicator.setConnectionInterrupted(false);
        hideConnectionLostOverlay();
        void recoverFreshInstallSession()
            .then(() => {
                if (activeRecoveryEpoch !== epoch || epoch !== disconnectEpoch) return;
                activeRecoveryEpoch = null;
            })
            .catch((error) => {
                if (activeRecoveryEpoch !== epoch || epoch !== disconnectEpoch) return;
                activeRecoveryEpoch = null;
                errorHandler.warn('AppLifecycle', 'Fresh install recovery during connection restore failed', ensureError(error));
            });
    };

    const markDisconnected = (): void => {
        invalidateConnectedRecovery();
        lastConnected = false;
        mainStateIndicator.setConnectionInterrupted(true);
        scheduleConnectionLostOverlay();
    };

    const unsubscribe = connectionStatus.subscribe((event) => {
        if (event.type === 'connected' || (event.connected && !lastConnected)) {
            markConnected();
            return;
        }
    });

    const wsClient = getWebSocketClient();
    const unsubscribeWebSocketEvents = subscribeManagedWebSocketContracts({
        label: 'LifecycleConnectionRuntime',
        subscribe: (eventType, handler) => wsClient.subscribe(eventType, handler),
        events: [
            createWebSocketContractBinding({
                contract: WEBSOCKET_EVENT_CONTRACTS.lifecycle.disconnected,
                handler: (payload) => {
                    if (payload.sessionClosure === 'rotate') {
                        invalidateConnectedRecovery();
                        void requireAuthManager()
                            .recoverRotatedSession()
                            .then(() => {
                                if (isMonitoring) wsClient.resumeAfterSessionRotation();
                            })
                            .catch((error) => {
                                if (!isMonitoring) return;
                                mainStateIndicator.setConnectionInterrupted(true);
                                errorHandler.warn('AppLifecycle', 'Rotated session recovery failed', ensureError(error));
                            });
                        return;
                    }
                    if (payload.sessionClosure === 'invalidate') {
                        invalidateConnectedRecovery();
                        clearConnectionLossTimer();
                        mainStateIndicator.setConnectionInterrupted(false);
                        hideConnectionLostOverlay();
                        void Promise.resolve()
                            .then(() => requireAuthManager().invalidateSession())
                            .catch((error) => errorHandler.warn('AppLifecycle', 'Revoked session cleanup failed', ensureError(error)));
                        return;
                    }
                    if (payload.reason === 'maintenance') {
                        invalidateConnectedRecovery();
                        clearConnectionLossTimer();
                        return;
                    }
                    if (isPageTerminating()) return;
                    markDisconnected();
                }
            })
        ]
    });

    return () => {
        isMonitoring = false;
        clearConnectionLossTimer();
        mainStateIndicator.setConnectionInterrupted(false);
        hideConnectionLostOverlay();
        unsubscribe();
        unsubscribeWebSocketEvents();
        tracker.cleanup();
    };
};

export { monitorLifecycleConnectionStatus };
