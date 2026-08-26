/* SoAI - Application lifecycle service and boot contracts [frontend/assets/ts/app/bootstrap/stages/applifecycle/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClient } from '@core/api/service.ts';
import type { AuthManager } from '@core/auth/public.ts';
import type { ComponentRegistry } from '@core/componentsupport/public.ts';
import type { ConnectionStatus } from '@core/connectionstatus/public.ts';
import type { LanguageService } from '@core/languageservice/service.ts';
import type { MainStatusMonitor } from '@core/mainstatusmonitor/public.ts';
import type { RouteDefinition } from '@core/routing/router/types.ts';
import type { MaintenanceState } from '@core/maintenanceCoordinator.ts';
import type { StreamManager } from '@core/realtime/streammanager/StreamManager.ts';
import type { Router } from '@core/routing/router/Router.ts';
import type { SoaiOsCapabilitiesService } from '@core/soaiOsAccess.ts';
import type { StateManager } from '@core/state/public.ts';
import type { ChartModulesAccess } from '@features/charts/chartModules.ts';
import type { OperationType } from '@features/overlays/public.ts';

export type RouteKey = string;
export type LifecycleRoute = RouteDefinition | string | null;

export interface LifecycleBackgroundOptions {
    forceDetection?: boolean | undefined;
}

export interface LayoutShellApi {
    initialize: (options?: { force?: boolean | undefined }) => Promise<boolean>;
    teardown: () => Promise<void>;
}

export interface TaskManagerApi {
    collapse: () => void;
}

export interface RestartOverlayApi {
    show: (type: OperationType) => void;
    hide: () => void;
    isVisible: boolean;
    currentType: OperationType | null;
}

export interface MainStateIndicatorApi {
    setConnectionInterrupted: (interrupted: boolean) => void;
}

export interface MaintenanceCoordinatorApi {
    getState: () => MaintenanceState;
}

export interface StorageService {
    ready: Promise<void>;
    getRedirectAfterLogin: () => string | null;
    clearRedirectAfterLogin: () => void;
    isWizardCompletionPending: () => boolean;
    isWizardCompleted: () => boolean;
    setWizardCompleted: () => Promise<void>;
}

export interface AppLifecycleBootPort {
    getIsRefreshScenario: () => boolean;
    finalizePreloader: () => Promise<void>;
    clearBootState: () => void;
}

export interface LifecycleRealtimePort {
    fetchModels: () => Promise<void>;
    fetchPlugins: () => Promise<void>;
}

export interface LifecycleBackgroundTaskPort {
    initialize: (options?: { force?: boolean | undefined }) => Promise<void>;
    applyForRoute: (route: LifecycleRoute) => void;
    reset?: (() => void) | undefined;
}

export interface AppLifecycleDependencies {
    api: ApiClient;
    auth: AuthManager;
    router: Router;
    storage: StorageService;
    languageService: LanguageService;
    streamManager: StreamManager;
    state: StateManager;
    realtime: LifecycleRealtimePort;
    connectionStatus: ConnectionStatus;
    restartOverlay: RestartOverlayApi;
    mainStateIndicator: MainStateIndicatorApi;
    maintenanceCoordinator: MaintenanceCoordinatorApi;
    mainStatusMonitor: MainStatusMonitor;
    chartModules: ChartModulesAccess;
    backgroundTasks: LifecycleBackgroundTaskPort;
    componentRegistry: ComponentRegistry;
    layoutShell: LayoutShellApi;
    taskManager: TaskManagerApi;
    soaiOsCapabilities: SoaiOsCapabilitiesService;
    boot: AppLifecycleBootPort;
}
