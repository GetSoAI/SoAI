/* SoAI - Frontend application lifecycle effects [frontend/assets/ts/app/bootstrap/stages/applifecycle/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { LayoutShellApi, LifecycleBackgroundOptions, LifecycleRoute } from '@app/bootstrap/stages/applifecycle/types.ts';
import { APIError } from '@core/apiError.ts';
import type { ApiClient } from '@core/api/service.ts';
import { getBranding } from '@core/branding/public.ts';
import type { ComponentRegistry } from '@core/componentsupport/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError, requireErrorMessage } from '@core/errors/coerce.ts';
import { isAbortError } from '@core/errors/abort.ts';
import type { LanguageService } from '@core/languageservice/service.ts';
import { ensureStreamManagerReady, type StreamManagerReadinessTarget } from '@core/realtime/streammanager/readiness.ts';
import type { StreamManager } from '@core/realtime/streammanager/StreamManager.ts';
import type { Router } from '@core/routing/router/Router.ts';
import type { SoaiOsCapabilitiesService } from '@core/soaiOsAccess.ts';
import type { ConnectionService } from '@core/types/streamTypes.ts';

interface InitializeLifecycleComponentsOptions {
    layoutShell: LayoutShellApi;
    componentRegistry: ComponentRegistry;
    skippedComponents: Set<string>;
    force?: boolean | undefined;
}

interface LifecycleDataHubState {
    initialization: Promise<void> | null;
    ready: boolean;
    connectionSubscription: (() => void) | null;
}

type LifecycleDataHubConnectionStatus = ConnectionService | null | undefined;

interface LifecycleDataHubStreamManager {
    resources: StreamManagerReadinessTarget;
    attachConnectionStatus: (connectionStatus: LifecycleDataHubConnectionStatus) => (() => void) | null;
}

interface LifecycleDataHubMainStatusMonitor {
    bindDataHub: () => Promise<boolean>;
}

interface InitializeLifecycleDataHubOptions {
    streamManager: LifecycleDataHubStreamManager;
    connectionStatus: LifecycleDataHubConnectionStatus;
    mainStatusMonitor: LifecycleDataHubMainStatusMonitor;
    state: LifecycleDataHubState;
}

interface LifecycleBackgroundTasks {
    initialize: (options?: { force?: boolean | undefined }) => Promise<void>;
    applyForRoute: (route: LifecycleRoute) => void;
    reset?: (() => void) | undefined;
}

export const ensureLifecycleCriticalServicesReady = async (storageReady: Promise<void>, languageService: LanguageService): Promise<void> => {
    const tasks: Promise<void>[] = [storageReady];
    if (!languageService.initialized) {
        if (!languageService.initializePromise) {
            languageService.initializePromise = languageService.initialize();
        }
        tasks.push(languageService.initializePromise);
    }
    await Promise.all(tasks);
};

export const destroyLifecycleRegisteredComponents = async (layoutShell: LayoutShellApi, componentRegistry: ComponentRegistry, router: Router): Promise<void> => {
    await layoutShell.teardown();
    await componentRegistry.destroyAll();
    componentRegistry.resetAll();
    await router.destroyCurrentPage();
};

export const initializeLifecycleComponents = async ({ layoutShell, componentRegistry, skippedComponents, force }: InitializeLifecycleComponentsOptions): Promise<void> => {
    await layoutShell.initialize({ force: force === true });

    const tasks: Promise<void>[] = [];
    componentRegistry.components.forEach((meta, name) => {
        if (skippedComponents.has(name)) {
            return;
        }
        if (!force && meta.initialized) {
            return;
        }
        tasks.push(componentRegistry.initialize(name, { force: force === true }));
    });
    await Promise.all(tasks);
};

export const initializeLifecycleDataHub = async ({ streamManager, connectionStatus, mainStatusMonitor, state }: InitializeLifecycleDataHubOptions): Promise<void> => {
    if (!state.initialization) {
        state.initialization = (async (): Promise<void> => {
            if (!state.ready) {
                if (state.connectionSubscription) {
                    state.connectionSubscription();
                    state.connectionSubscription = null;
                }
                state.connectionSubscription = streamManager.attachConnectionStatus(connectionStatus);
            }
            try {
                await ensureStreamManagerReady(streamManager.resources, { allowDiscovery: true });
            } catch (error) {
                state.ready = false;
                const runtimeError = ensureError(error);
                if (runtimeError instanceof APIError && runtimeError.status === 0) {
                    errorHandler.warn('AppLifecycle', 'Auto-resource bootstrap deferred due to offline backend', runtimeError);
                    throw runtimeError;
                }
                errorHandler.warn('AppLifecycle', 'Data hub bootstrap failed', runtimeError);
                throw runtimeError;
            }

            const statusBound = await mainStatusMonitor.bindDataHub();
            if (!statusBound) {
                state.ready = false;
                throw new Error('Main status monitor did not bind to the data hub');
            }
            state.ready = true;
        })().finally(() => {
            state.initialization = null;
        });
    }

    await state.initialization;
};

export const applyLifecycleBackground = async (backgroundTasks: LifecycleBackgroundTasks, isRefreshScenario: boolean, route: LifecycleRoute, options: LifecycleBackgroundOptions = {}): Promise<void> => {
    try {
        backgroundTasks.applyForRoute(route);
        await backgroundTasks.initialize({ force: isRefreshScenario || options.forceDetection === true });
    } catch (error) {
        const runtimeError = ensureError(error);
        if (isAbortError(runtimeError)) {
            return;
        }
        errorHandler.error('AppLifecycle', 'Failed to initialize background tasks', runtimeError);
    }
};

export const navigateLifecycleRoute = async (router: Router, route: string): Promise<void> => {
    await router.navigate(route, { pushState: false });
};

export const refreshLifecycleSoaiOsAccess = async (soaiOsCapabilities: SoaiOsCapabilitiesService): Promise<void> => {
    try {
        await soaiOsCapabilities.refreshAccess();
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.warn('AppLifecycle', 'Failed to refresh SoAI OS capability access', runtimeError);
    } finally {
        getBranding().forceRefresh();
    }
};

export const primeLifecycleBackendDiscovery = async (api: ApiClient): Promise<void> => {
    try {
        await api.whenReady({ allowDiscovery: true });
        const apiBaseUrl = api.getBaseUrl();
        if (!apiBaseUrl) {
            throw new Error('Backend base URL was not established');
        }
        getBranding().forceRefresh();
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.error('AppLifecycle', `Backend discovery failed: ${requireErrorMessage(runtimeError, '')}`, runtimeError);
        throw new Error('Unable to resolve backend endpoint');
    }
};

export const prepareLifecycleRefresh = (streamManager: StreamManager, backgroundTasks: LifecycleBackgroundTasks): void => {
    streamManager.resetAllResourceRuntimeState();
    if (backgroundTasks.reset) {
        backgroundTasks.reset();
    }
};

export type { LifecycleDataHubConnectionStatus, LifecycleDataHubMainStatusMonitor, LifecycleDataHubState, LifecycleDataHubStreamManager };
