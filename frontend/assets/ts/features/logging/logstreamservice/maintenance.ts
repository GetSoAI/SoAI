/* SoAI - Logging feature maintenance [frontend/assets/ts/features/logging/logstreamservice/maintenance.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { MaintenanceState } from '@core/maintenanceCoordinator.ts';
import { clearReconnectNotice } from '@features/logging/logstreamservice/events.ts';
import type { LogStreamLogger } from '@features/logging/logstreamservice/contracts.ts';
import type { LogStreamEvent, StreamSubscriptionHandle } from '@features/logging/logstreamservice/types.ts';
import type { LogStreamMutableState } from '@features/logging/logstreamservice/state.ts';

interface LogStreamMaintenanceContext {
    state: LogStreamMutableState;
    logger: Pick<LogStreamLogger, 'logError'>;
    notify: (event: LogStreamEvent) => void;
    teardownConnection: () => void;
    ensureConnection: () => Promise<StreamSubscriptionHandle | null>;
    clearTimer: (timerId: number | null | undefined) => void;
}

interface LogStreamMaintenanceSource {
    subscribe: (listener: (state: MaintenanceState) => void) => () => void;
}

const suspendLogStreamRecovery = (context: LogStreamMaintenanceContext): void => {
    context.state.connectionGeneration += 1;
    context.state.connectPromise = null;
    if (!context.state.recoverySuspended) {
        context.state.recoverySuspended = true;
    }
    clearReconnectNotice(context);
    if (context.state.subscribers.size > 0) {
        context.notify({ type: 'connection', status: 'reconnecting' });
    }
    context.teardownConnection();
};

const resumeLogStreamRecovery = (context: LogStreamMaintenanceContext): void => {
    if (!context.state.recoverySuspended) {
        return;
    }
    context.state.recoverySuspended = false;
    if (context.state.subscribers.size === 0) {
        return;
    }
    void context.ensureConnection().catch((error) => {
        context.logger.logError('Reconnection failed', error);
    });
};

const handleLogStreamMaintenanceChange = (context: LogStreamMaintenanceContext, state: MaintenanceState): void => {
    if (state.pausesTransport) {
        suspendLogStreamRecovery(context);
        return;
    }
    resumeLogStreamRecovery(context);
};

const subscribeLogStreamMaintenance = (source: LogStreamMaintenanceSource, context: LogStreamMaintenanceContext): (() => void) => {
    return source.subscribe((state) => {
        handleLogStreamMaintenanceChange(context, state);
    });
};

export { handleLogStreamMaintenanceChange, subscribeLogStreamMaintenance };
export type { LogStreamMaintenanceContext };
