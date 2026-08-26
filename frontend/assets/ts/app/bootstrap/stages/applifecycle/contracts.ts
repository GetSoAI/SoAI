/* SoAI - Application lifecycle authentication boundary contracts [frontend/assets/ts/app/bootstrap/stages/applifecycle/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { LifecycleBackgroundOptions, LifecycleRoute } from '@app/bootstrap/stages/applifecycle/types.ts';

interface LifecycleAuthHandlerHost {
    isBootstrapInProgress: () => boolean;
    handleLogin: () => Promise<void>;
    handleLogout: () => Promise<void>;
}

interface LifecycleAuthSubscriptions {
    unsubscribeLogin: () => void;
    unsubscribeLogout: () => void;
}

interface LifecycleLoginHost {
    setStateUninitialized: () => void;
    resetBranding: () => void;
    cleanupUiTracker: () => void;
    clearNavigationBootstrapSubscription: () => void;
    getCurrentRoute: () => string | null;
    shouldStayOnAuthRoute: (routeKey: string) => boolean;
    resolveAuthenticatedRoute: () => string;
    navigateToAuthenticatedRoute: (route: string) => Promise<void>;
    monitorConnectionStatus: () => void;
    toggleMainUI: (show: boolean) => void;
    refreshSoaiOsAccess: () => Promise<void>;
    clearConnectionSubscription: () => void;
    destroyRealtimeTransport: () => void;
    setupAuthenticatedSession: (options: { force?: boolean; initialRoute?: string | null }) => Promise<void>;
    resolveRouteKey: (route: LifecycleRoute | undefined) => string | null;
    ensureRouteRendered: (route: LifecycleRoute) => Promise<void>;
    applyBackground: (route: LifecycleRoute, options?: LifecycleBackgroundOptions) => Promise<void>;
}

interface LifecycleLogoutHost {
    clearAllTimers: () => void;
    clearNavigationBootstrapSubscription: () => void;
    clearConnectionSubscription: () => void;
    clearDataHubConnectionSubscription: () => void;
    clearRouterWarmupSubscription: () => void;
    clearSoaiOsAccess: () => void;
    resetConnectionStatus: () => void;
    resetMainStatusMonitor: () => void;
    resetStreamManager: () => void;
    resetBackgroundTasks: () => void;
    destroyRealtimeTransport: () => void;
    cleanupUiTracker: () => void;
    resetLifecycleState: () => void;
    destroyRegisteredComponents: () => Promise<void>;
    toggleMainUI: (show: boolean) => void;
    navigateToLoggedOutRoute: () => Promise<void>;
}

export type { LifecycleAuthHandlerHost, LifecycleAuthSubscriptions, LifecycleLoginHost, LifecycleLogoutHost };
