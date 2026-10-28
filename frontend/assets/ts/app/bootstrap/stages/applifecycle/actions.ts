/* SoAI - Frontend application lifecycle actions [frontend/assets/ts/app/bootstrap/stages/applifecycle/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resetAuthenticatedSessionServices } from '@app/bootstrap/stages/sessionServices.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { ResourceTracker } from '@core/resourcetracker/service.ts';
import { destroyWebSocketClient } from '@core/websocketclient/service.ts';

const cleanupLifecycleTracker = (tracker: ResourceTracker | null): ResourceTracker | null => {
    tracker?.cleanup();
    return null;
};

const clearLifecycleSubscription = (unsubscribe: (() => void) | null): (() => void) | null => {
    if (!unsubscribe) {
        return null;
    }
    unsubscribe();
    return null;
};

const clearLifecycleSubscriptionState = (unsubscribe: (() => void) | null, setUnsubscribe: (value: (() => void) | null) => void): void => {
    try {
        clearLifecycleSubscription(unsubscribe);
    } finally {
        setUnsubscribe(null);
    }
};

const runLifecycleStep = async (phase: 'login' | 'logout', label: string, action: () => void | Promise<void>): Promise<void> => {
    try {
        await action();
    } catch (error) {
        errorHandler.error('AppLifecycle', `${label} failed during ${phase}`, ensureError(error));
    }
};

interface LifecycleBootstrapResources {
    navigationBootstrapUnsubscribe: (() => void) | null;
    connectionSubscription: (() => void) | null;
    dataHubConnectionSubscription: (() => void) | null;
    routerWarmupUnsubscribe: (() => void) | null;
    uiTracker: ResourceTracker | null;
}

interface FailedBootstrapCleanupOptions extends LifecycleBootstrapResources {
    releaseAuthHandlers: () => void;
    clearSoaiOsAccess: () => void;
    resetConnectionStatus: () => void;
    resetMainStatusMonitor: () => void;
    resetStreamManager: () => void;
    resetBackgroundTasks: () => void;
    destroyRegisteredComponents: () => Promise<void>;
    destroyRouter: () => Promise<void>;
    setStateUninitialized: () => void;
    resetUiBoundState: () => void;
    clearBootstrapPromise: () => void;
    toggleMainUI: (show: boolean) => void;
}

const cleanupFailedBootstrap = async (options: FailedBootstrapCleanupOptions): Promise<void> => {
    clearLifecycleSubscription(options.navigationBootstrapUnsubscribe);
    clearLifecycleSubscription(options.connectionSubscription);
    clearLifecycleSubscription(options.dataHubConnectionSubscription);
    clearLifecycleSubscription(options.routerWarmupUnsubscribe);
    cleanupLifecycleTracker(options.uiTracker);
    options.releaseAuthHandlers();
    options.clearSoaiOsAccess();
    options.resetConnectionStatus();
    options.resetMainStatusMonitor();
    options.resetStreamManager();
    options.resetBackgroundTasks();
    destroyWebSocketClient();
    try {
        await resetAuthenticatedSessionServices();
        await options.destroyRegisteredComponents();
        await options.destroyRouter();
    } catch (error) {
        errorHandler.warn('AppLifecycle', 'Failed to cleanup router state after bootstrap failure', ensureError(error));
    }
    options.setStateUninitialized();
    options.resetUiBoundState();
    options.clearBootstrapPromise();
    options.toggleMainUI(false);
};

export { cleanupFailedBootstrap, cleanupLifecycleTracker, clearLifecycleSubscription, clearLifecycleSubscriptionState, runLifecycleStep };

export type { LifecycleBootstrapResources };
