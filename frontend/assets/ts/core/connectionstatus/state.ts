/* SoAI - Shared frontend connection status state [frontend/assets/ts/core/connectionstatus/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { INITIAL_RESTART_DELAY_MS } from '@core/connectionstatus/constants.ts';
import { createDefaultRestartInfo } from '@core/connectionstatus/health.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { ConnectionHold, RestartInfo, RestartSubscriber, StatusSubscriber, SystemInfo, Waiter } from '@core/connectionstatus/types.ts';

interface ConnectionStatusState {
    maintenanceUnsubscribe: (() => void) | null;
    unsubscribeHub: (() => void) | null;
    subscribers: Set<StatusSubscriber>;
    restartSubscribers: Set<RestartSubscriber>;
    connected: boolean;
    currentStatus: JsonObject | null;
    systemInfo: SystemInfo | null;
    waiters: Waiter[];
    isStarting: boolean;
    streamStartTask: Promise<void> | null;
    restartInfo: RestartInfo;
    bootstrapTracker: number | null;
    lastQueueDepth: number | null;
    restartTimer: number | null;
    nextRestartDelayMs: number;
    disconnectTimer: number | null;
    connectionHolds: Map<symbol, ConnectionHold>;
    maintenanceHold: boolean;
    lastConnectedEmitTimestamp: number | null;
    loginListener: (() => void) | null;
}

const createConnectionStatusState = (): ConnectionStatusState => ({
    maintenanceUnsubscribe: null,
    unsubscribeHub: null,
    subscribers: new Set<StatusSubscriber>(),
    restartSubscribers: new Set<RestartSubscriber>(),
    connected: false,
    currentStatus: null,
    systemInfo: null,
    waiters: [],
    isStarting: false,
    streamStartTask: null,
    restartInfo: createDefaultRestartInfo(),
    bootstrapTracker: null,
    lastQueueDepth: null,
    restartTimer: null,
    nextRestartDelayMs: INITIAL_RESTART_DELAY_MS,
    disconnectTimer: null,
    connectionHolds: new Map<symbol, ConnectionHold>(),
    maintenanceHold: false,
    lastConnectedEmitTimestamp: null,
    loginListener: null
});

export { createConnectionStatusState };
export type { ConnectionStatusState };
