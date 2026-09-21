/* SoAI - Frontend application core [frontend/assets/ts/app/bootstrap/stages/bootstrapCore.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { registerAllServices } from '@app/bootstrap/registerServices.ts';
import { AppLifecycle } from '@app/bootstrap/stages/applifecycle/AppLifecycle.ts';
import { resetInitializeCoreServices } from '@app/bootstrap/stages/initializeCoreServices.ts';
import { setBootstrapPhase } from '@app/bootstrap/stages/phases.ts';
import { detectNavigationReload, finalizePreloader } from '@app/bootstrap/stages/preloader.ts';
import type { BootstrapApi } from '@app/bootstrap/stages/types.ts';
import { getApiClient, resetApiClient } from '@core/api/service.ts';
import { getAuthManager } from '@core/auth/public.ts';
import { resetAuthManager } from '@core/auth/service.ts';
import { getBackgroundTasks, resetBackgroundTasksInstance } from '@core/backgroundtasks/service.ts';
import { getComponentRegistry } from '@core/componentsupport/public.ts';
import { requireConnectionStatus } from '@core/connectionstatus/public.ts';
import { requireDocument } from '@core/environment/public.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { resetLanguageRuntime, setLanguageRuntime } from '@core/languageservice/runtime.ts';
import { getLanguageService, resetLanguageService } from '@core/languageservice/service.ts';
import { MAIN_STATE_SERVICE_ID } from '@core/indicators/protocols.ts';
import { getMainStatusMonitor, resetMainStatusMonitor } from '@core/mainstatusmonitor/public.ts';
import { getMaintenanceCoordinator } from '@core/maintenanceCoordinator.ts';
import { RealtimeService, requireRealtimeService } from '@core/realtime/public.ts';
import { getStreamManager } from '@core/realtime/streammanager/public.ts';
import { resetRestartStateService } from '@core/restartStateService.ts';
import { resetCleanupManager } from '@core/resources.ts';
import { requireRouter } from '@core/routing/router/routerRuntime.ts';
import { resetKernel } from '@core/runtimeenv/kernel.ts';
import { resetWindowService } from '@core/runtimeenv/service.ts';
import { getServiceContainer } from '@core/serviceContainer.ts';
import { registerService } from '@core/serviceRegistration.ts';
import { isSoaiOsCapabilitiesService } from '@core/soaiOsAccess.ts';
import { getStateManager, resetStateManager } from '@core/state/public.ts';
import { isOperationType, RESTART_OVERLAY_SERVICE_ID, type OperationType } from '@features/overlays/public.ts';
import { TASK_MANAGER_SERVICE_ID } from '@core/tasks/protocols.ts';
import { isBoolean, isFunction, isObject, isThenable } from '@core/typeGuards.ts';
import { resetSecretInputToggleService } from '@core/ui/secretInput.ts';
import { resetSearchFieldActionService } from '@core/ui/searchField.ts';
import { resetTooltipService } from '@core/ui/tooltips/public.ts';
import { destroyWebSocketClient } from '@core/websocketclient/service.ts';
import { chartModulesAccess } from '@features/charts/chartModules.ts';

const BOOTSTRAP_MODULE_ID = 'core.bootstrap';

const clearBootState = (): void => {
    const root = requireDocument().documentElement;
    if (!root) {
        throw new Error('Document element must exist to clear boot state');
    }
    root.removeAttribute('data-soai-boot-state');
};

interface LayoutShellContract {
    initialize: (options?: { force?: boolean | undefined }) => Promise<boolean>;
    teardown: () => Promise<void>;
}

interface TaskManagerContract {
    collapse: () => void;
}

interface StorageContract {
    ready: Promise<void>;
    getRedirectAfterLogin: () => string | null;
    clearRedirectAfterLogin: () => void;
    isWizardCompletionPending: () => boolean;
    isWizardCompleted: () => boolean;
    setWizardCompleted: () => Promise<void>;
}

interface RestartOverlayContract {
    show: (type: OperationType) => void;
    hide: () => void;
    isVisible: boolean;
    currentType: OperationType | null;
}

interface MainStateIndicatorContract {
    setConnectionInterrupted: (interrupted: boolean) => void;
}

const isLayoutShellContract = <T>(value: T): value is T & LayoutShellContract => {
    if (!isObject(value)) {
        return false;
    }
    return 'initialize' in value && 'teardown' in value && isFunction(value.initialize) && isFunction(value.teardown);
};

const isTaskManagerContract = <T>(value: T): value is T & TaskManagerContract => {
    if (!isObject(value)) {
        return false;
    }
    return 'collapse' in value && isFunction(value.collapse);
};

const isStorageContract = <T>(value: T): value is T & StorageContract => {
    if (!isObject(value)) {
        return false;
    }
    return 'ready' in value && 'getRedirectAfterLogin' in value && 'clearRedirectAfterLogin' in value && 'isWizardCompletionPending' in value && 'isWizardCompleted' in value && 'setWizardCompleted' in value && isThenable(value.ready) && isFunction(value.getRedirectAfterLogin) && isFunction(value.clearRedirectAfterLogin) && isFunction(value.isWizardCompletionPending) && isFunction(value.isWizardCompleted) && isFunction(value.setWizardCompleted);
};

const isRestartOverlayContract = <T>(value: T): value is T & RestartOverlayContract => {
    if (!isObject(value)) {
        return false;
    }
    return 'show' in value && 'hide' in value && 'isVisible' in value && 'currentType' in value && isFunction(value.show) && isFunction(value.hide) && isBoolean(value.isVisible) && (value.currentType === null || isOperationType(value.currentType));
};

const isMainStateIndicatorContract = <T>(value: T): value is T & MainStateIndicatorContract => isObject(value) && 'setConnectionInterrupted' in value && isFunction(value.setConnectionInterrupted);

let bootstrapCoreConfigured = false;
let appLifecycleInstance: AppLifecycle | null = null;

const resetBootstrapCoreState = (): void => {
    appLifecycleInstance?.releaseAuthHandlers();
    appLifecycleInstance = null;
    bootstrapCoreConfigured = false;
};

const rollbackBootstrapCore = (): void => {
    appLifecycleInstance?.releaseAuthHandlers();
    destroyWebSocketClient();
    const serviceContainer = getServiceContainer();
    if (serviceContainer.has('core.realtime')) {
        const realtime = serviceContainer.get('core.realtime');
        if (realtime instanceof RealtimeService) {
            realtime.reset();
        }
    }
    if (serviceContainer.has('core.mainStatusMonitor')) {
        resetMainStatusMonitor();
    }
    resetBackgroundTasksInstance();
    resetRestartStateService();
    resetSecretInputToggleService();
    resetSearchFieldActionService();
    resetTooltipService();
    if (serviceContainer.has('core.auth')) {
        resetAuthManager();
    }
    if (serviceContainer.has('core.apiClient')) {
        resetApiClient();
    }
    resetKernel();
    resetWindowService();
    resetLanguageService();
    resetLanguageRuntime();
    if (serviceContainer.has('core.state')) {
        resetStateManager();
    }
    resetCleanupManager();
    resetInitializeCoreServices();
    serviceContainer.clear();
    resetBootstrapCoreState();
};

const ensureBootstrapCore = (): AppLifecycle => {
    if (bootstrapCoreConfigured && appLifecycleInstance) {
        return appLifecycleInstance;
    }
    try {
        const languageService = getLanguageService();
        setLanguageRuntime(languageService);

        registerAllServices(languageService);

        const serviceContainer = getServiceContainer();
        const shellCandidate = serviceContainer.get('core.layoutShell');
        if (!isLayoutShellContract(shellCandidate)) {
            throw new Error('core.layoutShell must expose initialize() and teardown()');
        }

        const taskManagerCandidate = serviceContainer.get(TASK_MANAGER_SERVICE_ID);
        if (!isTaskManagerContract(taskManagerCandidate)) {
            throw new Error(`${TASK_MANAGER_SERVICE_ID} must expose collapse()`);
        }

        const storageCandidate = serviceContainer.get('core.storage');
        if (!isStorageContract(storageCandidate)) {
            throw new Error('core.storage must expose ready/isWizardCompleted/setWizardCompleted');
        }
        const restartOverlayCandidate = serviceContainer.get(RESTART_OVERLAY_SERVICE_ID);
        if (!isRestartOverlayContract(restartOverlayCandidate)) {
            throw new Error(`${RESTART_OVERLAY_SERVICE_ID} must expose show()`);
        }
        const mainStateIndicatorCandidate = serviceContainer.get(MAIN_STATE_SERVICE_ID);
        if (!isMainStateIndicatorContract(mainStateIndicatorCandidate)) {
            throw new Error(`${MAIN_STATE_SERVICE_ID} must expose setConnectionInterrupted()`);
        }
        const soaiOsCapabilitiesCandidate = serviceContainer.get('core.soaiOsCapabilities');
        if (!isSoaiOsCapabilitiesService(soaiOsCapabilitiesCandidate)) {
            throw new Error('core.soaiOsCapabilities must expose the canonical SoAI OS capabilities contract');
        }

        const lifecycle = new AppLifecycle({
            api: getApiClient(),
            auth: getAuthManager(),
            router: requireRouter(),
            storage: storageCandidate,
            languageService,
            streamManager: getStreamManager(),
            state: getStateManager(),
            realtime: requireRealtimeService(),
            connectionStatus: requireConnectionStatus(),
            restartOverlay: restartOverlayCandidate,
            mainStateIndicator: mainStateIndicatorCandidate,
            maintenanceCoordinator: getMaintenanceCoordinator(),
            mainStatusMonitor: getMainStatusMonitor(),
            chartModules: chartModulesAccess,
            backgroundTasks: getBackgroundTasks(),
            componentRegistry: getComponentRegistry(),
            layoutShell: shellCandidate,
            taskManager: taskManagerCandidate,
            soaiOsCapabilities: soaiOsCapabilitiesCandidate,
            boot: {
                getIsRefreshScenario: () => detectNavigationReload(),
                finalizePreloader: () => finalizePreloader(),
                clearBootState: () => clearBootState()
            }
        });

        registerService('core.appLifecycle', lifecycle, { moduleId: 'core.appLifecycle', initialized: true });
        appLifecycleInstance = lifecycle;
        bootstrapCoreConfigured = true;
        setBootstrapPhase('core');
        return lifecycle;
    } catch (error) {
        rollbackBootstrapCore();
        throw ensureError(error);
    }
};

const ensureBootstrapServiceRegistered = (bootstrap: BootstrapApi): void => {
    if (getServiceContainer().has(BOOTSTRAP_MODULE_ID)) {
        return;
    }
    registerService(BOOTSTRAP_MODULE_ID, bootstrap, { moduleId: BOOTSTRAP_MODULE_ID, initialized: true });
};

export { clearBootState, ensureBootstrapCore, ensureBootstrapServiceRegistered };
