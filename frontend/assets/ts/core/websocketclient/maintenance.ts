/* SoAI - Shared frontend WebSocket client maintenance [frontend/assets/ts/core/websocketclient/maintenance.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { MaintenanceState } from '@core/maintenanceCoordinator.ts';
import { PERMANENT_SHUTDOWN_REASONS, type ConnectionState } from '@core/websocketclient/constants.ts';

interface WebSocketMaintenanceContext {
    baseUrl: string | null;
    connectionRequested: boolean;
    connectionState: ConnectionState;
}

interface WebSocketMaintenanceTransition {
    maintenanceHold: boolean;
    closeConnection: boolean;
    destroyConnection: boolean;
    reconnect: boolean;
}

const resolveWebSocketMaintenanceTransition = (state: MaintenanceState, context: WebSocketMaintenanceContext): WebSocketMaintenanceTransition => {
    if (state.pausesTransport) {
        return {
            maintenanceHold: true,
            closeConnection: true,
            destroyConnection: Boolean(state.reason && PERMANENT_SHUTDOWN_REASONS.has(state.reason)),
            reconnect: false
        };
    }
    return {
        maintenanceHold: false,
        closeConnection: false,
        destroyConnection: false,
        reconnect: Boolean(context.baseUrl && context.connectionRequested && context.connectionState === 'disconnected')
    };
};

export { resolveWebSocketMaintenanceTransition };
export type { WebSocketMaintenanceContext, WebSocketMaintenanceTransition };
