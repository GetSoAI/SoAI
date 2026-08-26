/* SoAI - Logging feature realtime history refresh [frontend/assets/ts/features/logging/logstreamservice/realtimeHistoryRefresh.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { DEFAULT_LOG_SOURCE } from '@features/logging/logstreamservice/constants.ts';
import type { LogStreamMutableState } from '@features/logging/logstreamservice/state.ts';
import type { StreamSubscriptionHandle } from '@features/logging/logstreamservice/types.ts';

interface RealtimeHistoryRefreshRuntime {
    state: LogStreamMutableState;
    ensureConnection: () => Promise<StreamSubscriptionHandle | null>;
}

const restartRealtimeHistoryWindow = async (runtime: RealtimeHistoryRefreshRuntime): Promise<void> => {
    if (runtime.state.snapshotMeta.source === DEFAULT_LOG_SOURCE) {
        return;
    }
    const expectedGeneration = runtime.state.connectionGeneration;
    const expectedSource = runtime.state.snapshotMeta.source;
    if (runtime.state.subscribers.size === 0) {
        return;
    }
    const connectPromise = runtime.state.connectPromise;
    if (connectPromise) {
        await connectPromise;
        if (expectedGeneration !== runtime.state.connectionGeneration || expectedSource !== runtime.state.snapshotMeta.source) {
            return;
        }
    }
    const handle = runtime.state.connectionHandle;
    if (!handle && !runtime.state.connectPromise) {
        return;
    }
    if (handle) {
        if (!handle.detach) {
            throw new Error('Log stream handle cannot detach for realtime history refresh');
        }
        handle.detach();
    }
    runtime.state.connectionHandle = null;
    runtime.state.isConnected = false;
    runtime.state.connectionStartedAt = 0;
    runtime.state.connectionGeneration += 1;
    runtime.state.connectPromise = null;
    await runtime.ensureConnection();
};

export { restartRealtimeHistoryWindow };
export type { RealtimeHistoryRefreshRuntime };
