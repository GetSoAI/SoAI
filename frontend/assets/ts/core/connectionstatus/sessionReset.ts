/* SoAI - Shared frontend connection status session reset [frontend/assets/ts/core/connectionstatus/sessionReset.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { INITIAL_RESTART_DELAY_MS } from '@core/connectionstatus/constants.ts';
import type { ConnectionStatusState } from '@core/connectionstatus/state.ts';

interface ResetConnectionStatusSessionOptions {
    state: ConnectionStatusState;
    stopStream: () => void;
    clearLoginListener: () => void;
    clearDisconnectTimer: () => void;
    clearRestartTimer: () => void;
    releaseAllConnectionHolds: () => void;
    rejectWaiters: (error: Error) => void;
    resetRestartInfoState: () => void;
}

const resetConnectionStatusSession = (options: ResetConnectionStatusSessionOptions): void => {
    options.stopStream();
    options.clearLoginListener();
    options.clearDisconnectTimer();
    options.clearRestartTimer();
    options.releaseAllConnectionHolds();
    options.rejectWaiters(new Error('Connection status reset'));
    options.state.connected = false;
    options.state.currentStatus = null;
    options.state.systemInfo = null;
    options.state.isStarting = false;
    options.state.streamStartTask = null;
    options.state.bootstrapTracker = null;
    options.state.lastQueueDepth = null;
    options.state.lastConnectedEmitTimestamp = null;
    options.state.nextRestartDelayMs = INITIAL_RESTART_DELAY_MS;
    options.resetRestartInfoState();
};

export { resetConnectionStatusSession };
