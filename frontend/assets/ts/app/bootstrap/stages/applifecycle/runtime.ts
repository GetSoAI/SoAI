/* SoAI - Frontend application runtime [frontend/assets/ts/app/bootstrap/stages/applifecycle/runtime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getFreshInstallRecovery } from '@app/bootstrap/stages/applifecycle/freshInstallRecovery.ts';
import { initializeLifecycleDataHub } from '@app/bootstrap/stages/applifecycle/effects.ts';
import { monitorLifecycleConnectionStatus } from '@app/bootstrap/stages/applifecycle/connectionMonitor.ts';
import { setupLifecycleEventListeners } from '@app/bootstrap/stages/applifecycle/lifecycleDomEvents.ts';
import { warmupCharts, resolveNavigationRoute } from '@app/bootstrap/stages/applifecycle/routing.ts';
import type { AppLifecycleDependencies, LifecycleRoute } from '@app/bootstrap/stages/applifecycle/types.ts';
import { initializeAuthenticatedSessionServices } from '@app/bootstrap/stages/sessionServices.ts';
import { onNavigationComplete } from '@core/navigationEvents.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';

interface AuthenticatedSessionRuntime {
    dependencies: AppLifecycleDependencies;
    force: boolean | undefined;
    initialRoute: string | null | undefined;
    getCurrentWarmupPromise: () => Promise<void> | null;
    setCurrentWarmupPromise: (value: Promise<void> | null) => void;
    chartWarmupRoutes: Set<string>;
    routerWarmupUnsubscribe: (() => void) | null;
    setRouterWarmupUnsubscribe: (value: (() => void) | null) => void;
    initializeDataHub: () => Promise<void>;
    initializeComponents: (options?: { force?: boolean }) => Promise<void>;
    setupEventListeners: () => void;
}

interface DataHubRuntimeState {
    initialization: Promise<void> | null;
    ready: boolean;
    connectionSubscription: (() => void) | null;
}

const initializeLifecycleDataHubRuntime = async (dependencies: AppLifecycleDependencies, dataHubState: DataHubRuntimeState): Promise<DataHubRuntimeState> => {
    const state = { ...dataHubState };
    const initializationTask = initializeLifecycleDataHub({
        streamManager: dependencies.streamManager,
        connectionStatus: dependencies.connectionStatus,
        mainStatusMonitor: dependencies.mainStatusMonitor,
        state
    });
    await initializationTask;
    return state;
};

const setupLifecycleUiEventRuntime = (dependencies: AppLifecycleDependencies, uiEventsBound: boolean, uiTracker: ResourceTracker | null): { uiEventsBound: boolean; uiTracker: ResourceTracker | null } => {
    if (uiEventsBound) {
        return { uiEventsBound, uiTracker };
    }
    const tracker = uiTracker ?? new ResourceTracker();
    setupLifecycleEventListeners({
        tracker,
        taskManager: dependencies.taskManager,
        state: dependencies.state,
        recoverFreshInstallSession: getFreshInstallRecovery(dependencies)
    });
    return { uiEventsBound: true, uiTracker: tracker };
};

const monitorLifecycleConnectionRuntime = (dependencies: AppLifecycleDependencies, connectionSubscription: (() => void) | null): (() => void) | null => {
    if (connectionSubscription) {
        return connectionSubscription;
    }
    const unsubscribe = monitorLifecycleConnectionStatus({
        connectionStatus: dependencies.connectionStatus,
        restartOverlay: dependencies.restartOverlay,
        mainStateIndicator: dependencies.mainStateIndicator,
        maintenanceCoordinator: dependencies.maintenanceCoordinator,
        recoverFreshInstallSession: getFreshInstallRecovery(dependencies)
    });
    return () => {
        unsubscribe();
    };
};

const bindLifecycleWarmupListener = (runtime: AuthenticatedSessionRuntime): void => {
    if (runtime.routerWarmupUnsubscribe) {
        return;
    }
    runtime.setRouterWarmupUnsubscribe(
        onNavigationComplete((detail) => {
            warmupLifecycleCharts(runtime, resolveNavigationRoute(detail));
        })
    );
};

const warmupLifecycleCharts = (runtime: Pick<AuthenticatedSessionRuntime, 'dependencies' | 'chartWarmupRoutes' | 'getCurrentWarmupPromise' | 'setCurrentWarmupPromise'>, route: LifecycleRoute): Promise<void> | undefined =>
    warmupCharts({
        route,
        chartWarmupRoutes: runtime.chartWarmupRoutes,
        chartModules: runtime.dependencies.chartModules,
        currentWarmupPromise: runtime.getCurrentWarmupPromise(),
        setWarmupPromise: runtime.setCurrentWarmupPromise
    });

const setupAuthenticatedLifecycleSession = async (runtime: AuthenticatedSessionRuntime): Promise<void> => {
    const activeRoute = runtime.initialRoute ?? runtime.dependencies.router.getCurrentRoute();
    await Promise.all([runtime.initializeDataHub(), initializeAuthenticatedSessionServices()]);
    await runtime.initializeComponents({ force: runtime.force === true });
    warmupLifecycleCharts(runtime, activeRoute);
    bindLifecycleWarmupListener(runtime);
    runtime.setupEventListeners();
};

export { bindLifecycleWarmupListener, initializeLifecycleDataHubRuntime, monitorLifecycleConnectionRuntime, setupAuthenticatedLifecycleSession, setupLifecycleUiEventRuntime, warmupLifecycleCharts };
