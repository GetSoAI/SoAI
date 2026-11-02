/* SoAI - Frontend application session [frontend/assets/ts/app/bootstrap/stages/applifecycle/session.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { cleanupLifecycleTracker, clearLifecycleSubscriptionState, runLifecycleStep } from '@app/bootstrap/stages/applifecycle/actions.ts';
import type { LifecycleLoginHost, LifecycleLogoutHost } from '@app/bootstrap/stages/applifecycle/contracts.ts';
import { ensureRouteRendered, resolveLoggedOutRoute, resolveNavigationRoute, resolveRouteKey } from '@app/bootstrap/stages/applifecycle/routing.ts';
import { resetAuthenticatedSessionServices } from '@app/bootstrap/stages/sessionServices.ts';
import type { AppLifecycleDependencies, LifecycleBackgroundOptions, LifecycleRoute } from '@app/bootstrap/stages/applifecycle/types.ts';
import { getBranding } from '@core/branding/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { runCleanup } from '@core/lifecycle/cleanup.ts';
import { onFocusedNavigation } from '@core/navigationEvents.ts';
import type { ResourceTracker } from '@core/resourcetracker/service.ts';
import { isAuthRouteComponent } from '@core/routing/router/authRouteTarget.ts';
import { destroyWebSocketClient } from '@core/websocketclient/service.ts';

interface AppLifecycleLoginOptions {
    dependencies: AppLifecycleDependencies;
    uiTracker: ResourceTracker | null;
    setUiTracker: (value: ResourceTracker | null) => void;
    navigationBootstrapUnsubscribe: (() => void) | null;
    setNavigationBootstrapUnsubscribe: (value: (() => void) | null) => void;
    setStateUninitialized: () => void;
    monitorConnectionStatus: () => void;
    toggleMainUI: (show: boolean, animateEntrance?: boolean) => void;
    shouldStayOnAuthRoute: (routeKey: string) => boolean;
    resolveAuthenticatedRoute: () => string;
    navigateToAuthenticatedRoute: (route: string) => Promise<void>;
    refreshSoaiOsAccess: () => Promise<void>;
    connectionSubscription: (() => void) | null;
    setConnectionSubscription: (value: (() => void) | null) => void;
    setupAuthenticatedSession: (options: { force?: boolean; initialRoute?: string | null }) => Promise<void>;
    applyBackground: (route: LifecycleRoute, options?: LifecycleBackgroundOptions) => Promise<void>;
}

interface AppLifecycleLogoutOptions {
    routeDisposition: 'navigate' | 'defer';
    dependencies: AppLifecycleDependencies;
    uiTracker: ResourceTracker | null;
    setUiTracker: (value: ResourceTracker | null) => void;
    navigationBootstrapUnsubscribe: (() => void) | null;
    setNavigationBootstrapUnsubscribe: (value: (() => void) | null) => void;
    connectionSubscription: (() => void) | null;
    setConnectionSubscription: (value: (() => void) | null) => void;
    dataHubConnectionSubscription: (() => void) | null;
    setDataHubConnectionSubscription: (value: (() => void) | null) => void;
    routerWarmupUnsubscribe: (() => void) | null;
    setRouterWarmupUnsubscribe: (value: (() => void) | null) => void;
    resetLifecycleState: () => void;
    destroyRegisteredComponents: () => Promise<void>;
    toggleMainUI: (show: boolean) => void;
}

export const handleLifecycleLogin = async ({ isCurrent, setStateUninitialized, resetBranding, cleanupUiTracker, clearNavigationBootstrapSubscription, getCurrentRoute, shouldStayOnAuthRoute, resolveAuthenticatedRoute, navigateToAuthenticatedRoute, monitorConnectionStatus, toggleMainUI, refreshSoaiOsAccess, clearConnectionSubscription, destroyRealtimeTransport, setupAuthenticatedSession, resolveRouteKey, ensureRouteRendered, applyBackground }: LifecycleLoginHost): Promise<void> => {
    if (!isCurrent()) return;
    const animateShellEntrance = isAuthRouteComponent(resolveRouteKey(getCurrentRoute()) ?? '');
    let handoffCompleted = false;
    let handoffInProgress = false;
    let unsubscribe: (() => void) | null = null;

    const disposeNavigationSubscription = (): void => {
        const dispose = unsubscribe;
        unsubscribe = null;
        runCleanup(dispose, (runtimeError) => {
            errorHandler.warn('AppLifecycle', 'Login navigation subscription cleanup failed', runtimeError);
        });
    };

    const sessionSetupTask = (async (): Promise<void> => {
        await refreshSoaiOsAccess();
        if (!isCurrent()) return;
        await runLifecycleStep('login', 'Connection subscription cleanup', clearConnectionSubscription);
        if (!isCurrent()) return;
        await runLifecycleStep('login', 'Realtime transport reset', destroyRealtimeTransport);
        if (!isCurrent()) return;
        await setupAuthenticatedSession({ force: true, initialRoute: null });
        if (!isCurrent()) return;
        monitorConnectionStatus();
    })();

    const completeUiHandoff = async (route: LifecycleRoute): Promise<void> => {
        if (!isCurrent()) {
            disposeNavigationSubscription();
            return;
        }
        if (handoffCompleted || handoffInProgress) {
            return;
        }
        await sessionSetupTask;
        if (!isCurrent()) {
            disposeNavigationSubscription();
            return;
        }
        if (handoffCompleted || handoffInProgress) {
            return;
        }
        handoffInProgress = true;
        try {
            let key = resolveRouteKey(route);
            if (!key) {
                key = resolveAuthenticatedRoute();
            }
            if (isAuthRouteComponent(key)) {
                if (!shouldStayOnAuthRoute(key)) key = resolveAuthenticatedRoute();
                await navigateToAuthenticatedRoute(key);
                if (!isCurrent()) {
                    disposeNavigationSubscription();
                    return;
                }
            }
            handoffCompleted = true;
            disposeNavigationSubscription();
            setStateUninitialized();
            resetBranding();
            cleanupUiTracker();
            clearNavigationBootstrapSubscription();
            if (!isCurrent()) return;
            toggleMainUI(true, animateShellEntrance && !isAuthRouteComponent(key));
            if (!isCurrent()) return;
            await ensureRouteRendered(key);
            if (!isCurrent()) return;
            await applyBackground(key, { forceDetection: true });
        } finally {
            if (!handoffCompleted) {
                handoffInProgress = false;
            }
        }
    };

    unsubscribe = onFocusedNavigation((detail) => {
        void completeUiHandoff(resolveNavigationRoute(detail)).catch((error) => {
            const runtimeError = ensureError(error);
            errorHandler.error('AppLifecycle', 'Login navigation handler failed', runtimeError);
        });
    });

    await sessionSetupTask;
    await completeUiHandoff(getCurrentRoute());
};

export const handleLifecycleLogout = async ({ clearAllTimers, clearNavigationBootstrapSubscription, clearConnectionSubscription, clearDataHubConnectionSubscription, clearRouterWarmupSubscription, clearSoaiOsAccess, resetConnectionStatus, resetMainStatusMonitor, resetStreamManager, resetBackgroundTasks, destroyRealtimeTransport, cleanupUiTracker, resetLifecycleState, destroyRegisteredComponents, toggleMainUI, navigateToLoggedOutRoute }: LifecycleLogoutHost): Promise<void> => {
    await runLifecycleStep('logout', 'Lifecycle pre-cleanup', () => {
        clearAllTimers();
        clearNavigationBootstrapSubscription();
        clearConnectionSubscription();
        clearDataHubConnectionSubscription();
        clearRouterWarmupSubscription();
        clearSoaiOsAccess();
        resetConnectionStatus();
        resetMainStatusMonitor();
        resetStreamManager();
        resetBackgroundTasks();
        destroyRealtimeTransport();
    });
    await runLifecycleStep('logout', 'Authenticated session service reset', () => resetAuthenticatedSessionServices());
    await runLifecycleStep('logout', 'UI tracker cleanup', () => {
        cleanupUiTracker();
    });
    await runLifecycleStep('logout', 'Lifecycle state reset', () => {
        resetLifecycleState();
    });
    await runLifecycleStep('logout', 'Registered component teardown', () => destroyRegisteredComponents());
    toggleMainUI(false);
    await navigateToLoggedOutRoute();
};

export const runAppLifecycleLogin = async (options: AppLifecycleLoginOptions): Promise<void> => {
    const epoch = options.dependencies.auth.authEpoch;
    await handleLifecycleLogin({
        isCurrent: () => options.dependencies.auth.authEpoch === epoch && options.dependencies.auth.isAuthenticated,
        setStateUninitialized: options.setStateUninitialized,
        resetBranding: () => {
            getBranding().initialized = false;
        },
        cleanupUiTracker: () => {
            options.setUiTracker(cleanupLifecycleTracker(options.uiTracker));
        },
        clearNavigationBootstrapSubscription: () => {
            clearLifecycleSubscriptionState(options.navigationBootstrapUnsubscribe, options.setNavigationBootstrapUnsubscribe);
        },
        getCurrentRoute: () => options.dependencies.router.getCurrentRoute() ?? options.dependencies.router.getRouteFromHash(),
        shouldStayOnAuthRoute: options.shouldStayOnAuthRoute,
        resolveAuthenticatedRoute: options.resolveAuthenticatedRoute,
        navigateToAuthenticatedRoute: options.navigateToAuthenticatedRoute,
        monitorConnectionStatus: options.monitorConnectionStatus,
        toggleMainUI: options.toggleMainUI,
        refreshSoaiOsAccess: options.refreshSoaiOsAccess,
        clearConnectionSubscription: () => {
            clearLifecycleSubscriptionState(options.connectionSubscription, options.setConnectionSubscription);
        },
        destroyRealtimeTransport: () => {
            options.dependencies.streamManager.resetAllResourceRuntimeState();
            destroyWebSocketClient();
        },
        setupAuthenticatedSession: options.setupAuthenticatedSession,
        resolveRouteKey,
        ensureRouteRendered: (route) =>
            ensureRouteRendered({
                route,
                router: options.dependencies.router
            }),
        applyBackground: options.applyBackground
    });
};

export const runAppLifecycleLogout = async (options: AppLifecycleLogoutOptions): Promise<void> => {
    await handleLifecycleLogout({
        clearAllTimers: () => {
            options.uiTracker?.clearAllTimers();
        },
        clearNavigationBootstrapSubscription: () => {
            clearLifecycleSubscriptionState(options.navigationBootstrapUnsubscribe, options.setNavigationBootstrapUnsubscribe);
        },
        clearConnectionSubscription: () => {
            clearLifecycleSubscriptionState(options.connectionSubscription, options.setConnectionSubscription);
        },
        clearDataHubConnectionSubscription: () => {
            clearLifecycleSubscriptionState(options.dataHubConnectionSubscription, options.setDataHubConnectionSubscription);
        },
        clearRouterWarmupSubscription: () => {
            clearLifecycleSubscriptionState(options.routerWarmupUnsubscribe, options.setRouterWarmupUnsubscribe);
        },
        clearSoaiOsAccess: () => options.dependencies.soaiOsCapabilities.clearAccess(),
        resetConnectionStatus: () => options.dependencies.connectionStatus.reset(),
        resetMainStatusMonitor: () => options.dependencies.mainStatusMonitor.reset(),
        resetStreamManager: () => options.dependencies.streamManager.reset(),
        resetBackgroundTasks: () => {
            if (options.dependencies.backgroundTasks.reset) {
                options.dependencies.backgroundTasks.reset();
            }
        },
        destroyRealtimeTransport: () => destroyWebSocketClient(),
        cleanupUiTracker: () => {
            options.setUiTracker(cleanupLifecycleTracker(options.uiTracker));
        },
        resetLifecycleState: options.resetLifecycleState,
        destroyRegisteredComponents: options.destroyRegisteredComponents,
        toggleMainUI: options.toggleMainUI,
        navigateToLoggedOutRoute: async () => {
            if (options.routeDisposition === 'navigate') await options.dependencies.router.navigate(resolveLoggedOutRoute(options.dependencies.auth.getWizardStatusSnapshot()), { force: true });
        }
    });
};
