/* SoAI - Shared main status monitor contracts [frontend/assets/ts/core/mainstatusmonitor/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SystemStatusResource } from '@core/realtime/streammanager/resourceRegistry.ts';
import type { ResourceSnapshot } from '@core/realtime/streammanager/types.ts';
import type { STATUS } from '@core/realtime/streammanager/resources/ids.ts';

type StatusCallback = (state: string) => void;

interface AuthManagerInterface {
    onLogin: (callback: () => void) => (() => void) | void;
    isAuthenticated: boolean;
}

type StatusStreamId = typeof STATUS;
type StreamSnapshot = ResourceSnapshot<SystemStatusResource>;

interface StreamManagerInterface {
    resources: {
        ensureReady: (options: { allowDiscovery: boolean }) => Promise<void>;
        getResource: (streamId: StatusStreamId, options: { state: true }) => StreamSnapshot | null;
        ensureResourceStarted: (streamId: StatusStreamId, options?: { throwOnError?: boolean }) => Promise<SystemStatusResource | null>;
    };
    subscriptions: {
        subscribeResourceState: (streamId: StatusStreamId, callback: (snapshot: StreamSnapshot) => void) => (() => void) | void;
    };
}

export type { AuthManagerInterface, StatusCallback, StreamManagerInterface, StreamSnapshot };
