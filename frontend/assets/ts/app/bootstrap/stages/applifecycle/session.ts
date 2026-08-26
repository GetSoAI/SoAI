/* SoAI - Frontend application session [frontend/assets/ts/app/bootstrap/stages/applifecycle/session.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { cleanupLifecycleTracker, clearLifecycleSubscriptionState, runLifecycleStep } from '@app/bootstrap/stages/applifecycle/actions.ts';
import type { LifecycleAuthHandlerHost, LifecycleAuthSubscriptions, LifecycleLoginHost, LifecycleLogoutHost } from '@app/bootstrap/stages/applifecycle/contracts.ts';
import { ensureRouteRendered, resolveLoggedOutRoute, resolveNavigationRoute, resolveRouteKey } from '@app/bootstrap/stages/applifecycle/routing.ts';
import { resetAuthenticatedSessionServices } from '@app/bootstrap/stages/sessionServices.ts';
import type { AppLifecycleDependencies, LifecycleBackgroundOptions, LifecycleRoute } from '@app/bootstrap/stages/applifecycle/types.ts';
import { getBranding } from '@core/branding/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { runCleanup } from '@core/lifecycle/cleanup.ts';
import { onNavigationComplete } from '@core/navigationEvents.ts';
import type { ResourceTracker } from '@core/resourcetracker/service.ts';
import { isAuthRouteComponent } from '@core/routing/router/authRouteTarget.ts';
import { destroyWebSocketClient } from '@core/websocketclient/service.ts';

interface AuthLifecycleEvents {
    onLogin: (callback: () => void | Promise<void>) => (() => void) | void;
    onLogout: (callback: () => void | Promise<void>) => (() => void) | void;
}

interface RegisterLifecycleAuthHandlersOptions {
    auth: AuthLifecycleEvents;
    host: LifecycleAuthHandlerHost;
}

class LifecycleAuthSession {
    #unsubscribeLogin: (() => void) | null = null;
    #unsubscribeLogout: (() => void) | null = null;
    #registered = false;

    register({ auth, host }: RegisterLifecycleAuthHandlersOptions): void {
        if (this.#registered) {
            return;
        }
        const subscriptions = registerLifecycleAuthHandlers({ auth, host });
        this.#unsubscribeLogin = subscriptions.unsubscribeLogin;
        this.#unsubscribeLogout = subscriptions.unsubscribeLogout;
        this.#registered = true;
    }

    release(): void {
        const unsubscribeLogin = this.#unsubscribeLogin;
        const unsubscribeLogout = this.#unsubscribeLogout;
        this.#unsubscribeLogin = null;
        this.#unsubscribeLogout = null;
        runCleanup(unsubscribeLogin, (runtimeError) => {
            errorHandler.warn('AppLifecycle', 'Login subscription cleanup failed', runtimeError);
        });
        runCleanup(unsubscribeLogout, (runtimeError) => {
            errorHandler.warn('AppLifecycle', 'Logout subscription cleanup failed', runtimeError);
        });
        this.#registered = false;
    }
}

interface AppLifecycleLoginOptions {
    dependencies: AppLifecycleDependencies;
    uiTracker: ResourceTracker | null;
    setUiTracker: (value: ResourceTracker | null) => void;
    navigationBootstrapUnsubscribe: (() => void) | null;
    setNavigationBootstrapUnsubscribe: (value: (() => void) | null) => void;
    setStateUninitialized: () => void;
    monitorConnectionStatus: () => void;
    toggleMainUI: (show: boolean) => void;
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

export const registerLifecycleAuthHandlers = ({ auth, host }: RegisterLifecycleAuthHandlersOptions): LifecycleAuthSubscriptions => {
    let transitionTail: Promise<void> = Promise.resolve();
    const enqueueTransition = (transition: () => Promise<void>, label: string): void => {
        const task = transitionTail.then(transition, transition);
        transitionTail = task;
        void task.catch((error) => {
            errorHandler.error('AppLifecycle', `${label} handler failed`, ensureError(error));
        });
    };
    const unsubscribeLogin = auth.onLogin(() => {
        if (host.isBootstrapInProgress()) {
            return;
        }
        enqueueTransition(host.handleLogin, 'Login');
    });

    const unsubscribeLogout = auth.onLogout(() => {
        enqueueTransition(host.handleLogout, 'Logout');
    });

    return {
        unsubscribeLogin: typeof unsubscribeLogin === 'function' ? unsubscribeLogin : () => {},
        unsubscribeLogout: typeof unsubscribeLogout === 'function' ? unsubscribeLogout : () => {}
    };
};

export const handleLifecycleLogin = async ({ setStateUninitialized, resetBranding, cleanupUiTracker, clearNavigationBootstrapSubscription, getCurrentRoute, shouldStayOnAuthRoute, resolveAuthenticatedRoute, navigateToAuthenticatedRoute, monitorConnectionStatus, toggleMainUI, refreshSoaiOsAccess, clearConnectionSubscription, destroyRealtimeTransport, setupAuthenticatedSession, resolveRouteKey, ensureRouteRendered, applyBackground }: LifecycleLoginHost): Promise<void> => {
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
        await runLifecycleStep('login', 'Connection subscription cleanup', clearConnectionSubscription);
        await runLifecycleStep('login', 'Realtime transport reset', destroyRealtimeTransport);
        await setupAuthenticatedSession({ force: true, initialRoute: null });
        monitorConnectionStatus();
    })();

    const completeUiHandoff = async (route: LifecycleRoute): Promise<void> => {
        if (handoffCompleted || handoffInProgress) {
            return;
        }
        await sessionSetupTask;
        if (handoffCompleted || handoffInProgress) {
            return;
        }
        handoffInProgress = true;
        try {
            let key = resolveRouteKey(route);
            if (!key) {
                key = resolveAuthenticatedRoute();
            }
            if (isAuthRouteComponent(key) && !shouldStayOnAuthRoute(key)) {
                key = resolveAuthenticatedRoute();
                await navigateToAuthenticatedRoute(key);
            }
            handoffCompleted = true;
            disposeNavigationSubscription();
            setStateUninitialized();
            resetBranding();
            cleanupUiTracker();
            clearNavigationBootstrapSubscription();
            toggleMainUI(true);
            await ensureRouteRendered(key);
            await applyBackground(key, { forceDetection: true });
        } finally {
            if (!handoffCompleted) {
                handoffInProgress = false;
            }
        }
    };

    unsubscribe = onNavigationComplete((detail) => {
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
    await handleLifecycleLogin({
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
        navigateToLoggedOutRoute: () => options.dependencies.router.navigate(resolveLoggedOutRoute(options.dependencies.auth.getWizardStatusSnapshot()), { force: true })
    });
};

export { LifecycleAuthSession };
