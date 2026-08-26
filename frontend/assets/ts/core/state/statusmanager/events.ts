/* SoAI - Shared state status manager events [frontend/assets/ts/core/state/statusmanager/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction, isObject } from '@core/typeGuards.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import type { StatusStreamSnapshot } from '@core/state/statusTypes.ts';
import type { StreamManager } from '@core/state/statusmanager/contracts.ts';
import type { ErrorLogger, StatusStreamMonitorPayload, StreamMonitorResult } from '@core/state/statusmanager/internalContracts.ts';
import { readSnapshotValue } from '@core/state/statusmanager/mappers.ts';
import { ensureError } from '@core/errors/coerce.ts';

const startStatusStreamMonitor = ({ streamManager, streamId, handler, onError }: { streamManager: StreamManager; streamId: string; handler: (snapshot: StatusStreamMonitorPayload) => void; onError: ErrorLogger }): StreamMonitorResult => {
    let unsub: (() => void) | null = null;
    let disposed = false;

    const statusHandler = (snapshot: StatusStreamSnapshot): void => {
        if (disposed) {
            return;
        }
        const safeValue = readSnapshotValue(snapshot);
        handler({ snapshot, rawValue: safeValue });
    };

    try {
        const initialState = streamManager.resources.getResource(streamId, { state: true });
        if (isObject(initialState) && 'value' in initialState) {
            const rawValue = readSnapshotValue(initialState);
            handler({ snapshot: { value: rawValue }, rawValue });
        }

        const subscription = streamManager.subscriptions.subscribeResourceState(streamId, statusHandler, { immediate: false });
        if (isFunction(subscription)) {
            unsub = subscription;
        }
    } catch (error) {
        const runtimeError = ensureError(error);
        onError('StatusManager', 'Global status monitoring failed to start', runtimeError);
    }

    return {
        stop: (): void => {
            disposed = true;
            if (isFunction(unsub)) {
                unsub();
            }
            unsub = null;
        }
    };
};

const bindAuthEvents = ({
    auth,
    resources,
    onLogin,
    onLogout,
    onError
}: {
    auth: {
        onLogin: (callback: () => void) => () => void;
        onLogout: (callback: () => void) => () => void;
    };
    resources: ResourceTracker;
    onLogin: () => void;
    onLogout: () => void;
    onError: (error: Error) => void;
}): void => {
    try {
        const loginDisposer = auth.onLogin(onLogin);
        const logoutDisposer = auth.onLogout(onLogout);
        if (isFunction(loginDisposer)) {
            resources.track(loginDisposer, cleanupAuthEventDisposer);
        }
        if (isFunction(logoutDisposer)) {
            resources.track(logoutDisposer, cleanupAuthEventDisposer);
        }
    } catch (error) {
        resources.cleanup();
        const runtimeError = ensureError(error);
        onError(runtimeError);
    }
};

const cleanupAuthEventDisposer = (dispose: () => void): void => {
    try {
        dispose();
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.warn('StatusManager', 'Failed to cleanup auth event disposer', runtimeError);
    }
};

export { bindAuthEvents, startStatusStreamMonitor };
