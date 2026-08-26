/* SoAI - Frontend application lifecycle bootstrap [frontend/assets/ts/app/bootstrap/stages/applifecycle/bootstrap.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { cleanupFailedBootstrap } from '@app/bootstrap/stages/applifecycle/actions.ts';
import { prepareLifecycleEnvironment } from '@app/bootstrap/stages/applifecycle/dom.ts';
import { ensureLifecycleCriticalServicesReady, navigateLifecycleRoute, prepareLifecycleRefresh, primeLifecycleBackendDiscovery } from '@app/bootstrap/stages/applifecycle/effects.ts';
import { ensureRouteRendered } from '@app/bootstrap/stages/applifecycle/routing.ts';
import type { AppLifecycleDependencies, LifecycleBackgroundOptions, LifecycleRoute } from '@app/bootstrap/stages/applifecycle/types.ts';
import { getElementByIdStrict } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isLifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import { onNavigationComplete } from '@core/navigationEvents.ts';
import type { ResourceTracker } from '@core/resourcetracker/service.ts';
import { resetSaveHeaderActionState } from '@core/save/public.ts';
import { isObject, isString } from '@core/typeGuards.ts';

interface RunAppLifecycleBootstrapOptions {
    dependencies: AppLifecycleDependencies;
    isRefreshScenario: boolean;
    navigationBootstrapUnsubscribe: (() => void) | null;
    connectionSubscription: (() => void) | null;
    dataHubConnectionSubscription: (() => void) | null;
    routerWarmupUnsubscribe: (() => void) | null;
    uiTracker: ResourceTracker | null;
    setNavigationBootstrapUnsubscribe: (value: (() => void) | null) => void;
    setConnectionSubscription: (value: (() => void) | null) => void;
    setDataHubConnectionSubscription: (value: (() => void) | null) => void;
    setRouterWarmupUnsubscribe: (value: (() => void) | null) => void;
    setUiTracker: (value: ResourceTracker | null) => void;
    setStateUninitialized: () => void;
    resetUiBoundState: () => void;
    clearBootstrapPromise: () => void;
    registerAuthHandlers: () => void;
    releaseAuthHandlers: () => void;
    refreshSoaiOsAccess: () => Promise<void>;
    resolveInitialRoute: (isAuthenticated: boolean, needsWizard: boolean) => Promise<string>;
    setupAuthenticatedSession: (options: { force?: boolean; initialRoute?: string | null }) => Promise<void>;
    applyBackground: (route: LifecycleRoute, options?: LifecycleBackgroundOptions) => Promise<void>;
    monitorConnectionStatus: () => void;
    toggleMainUI: (show: boolean) => void;
    destroyRegisteredComponents: () => Promise<void>;
    renderInitializationError: (error: Error) => void;
}

const runAppLifecycleBootstrap = async (options: RunAppLifecycleBootstrapOptions): Promise<void> => {
    const { dependencies } = options;
    try {
        await primeLifecycleBackendDiscovery(dependencies.api);
        if (options.isRefreshScenario) {
            prepareLifecycleRefresh(dependencies.streamManager, dependencies.backgroundTasks);
        }
        prepareLifecycleEnvironment();
        await ensureLifecycleCriticalServicesReady(dependencies.storage.ready, dependencies.languageService);
        if (!dependencies.languageService.initialized) {
            throw new Error('Language service must be initialized before router setup');
        }
        if (!dependencies.router.initialized) {
            dependencies.router.initialize();
        }
        if (!dependencies.router.contentContainer) {
            dependencies.router.setContentContainer(getElementByIdStrict('main-content'));
        }
        const needsWizard = (await dependencies.auth.checkWizardStatus()) === true;
        const wizardStatus = dependencies.auth.getWizardStatusSnapshot();
        await dependencies.auth.initialize({ wizardState: wizardStatus ?? null, skipSessionProbe: needsWizard });
        options.registerAuthHandlers();
        const isAuthenticated = dependencies.auth.isAuthenticated;
        if (isAuthenticated) {
            await options.refreshSoaiOsAccess();
        } else {
            dependencies.soaiOsCapabilities.clearAccess();
        }
        const finalRoute = await options.resolveInitialRoute(isAuthenticated, needsWizard);
        if (isAuthenticated) {
            await options.setupAuthenticatedSession({ force: options.isRefreshScenario, initialRoute: finalRoute });
        }
        if (!finalRoute) {
            throw new Error('Route skeleton rendering requires a non-empty route identifier');
        }
        dependencies.router.getPageOutlet().setSkeleton(finalRoute);
        await navigateLifecycleRoute(dependencies.router, finalRoute);
        const renderedRoute = dependencies.router.getCurrentRoute() ?? finalRoute;
        await ensureRouteRendered({ route: renderedRoute, router: dependencies.router });
        await options.applyBackground(renderedRoute);
        if (!options.navigationBootstrapUnsubscribe) {
            options.setNavigationBootstrapUnsubscribe(
                onNavigationComplete(async (detail) => {
                    try {
                        resetSaveHeaderActionState();
                        const navigationRoute = isObject(detail) ? detail['route'] : null;
                        await options.applyBackground(isString(navigationRoute) ? navigationRoute : dependencies.router.getCurrentRoute());
                    } catch (error) {
                        errorHandler.error('AppLifecycle', 'Navigation background failed', ensureError(error));
                    }
                })
            );
        }
        options.monitorConnectionStatus();
        void dependencies.boot.finalizePreloader().catch((error) => {
            errorHandler.warn('AppLifecycle', 'Preloader finalization failed after bootstrap', ensureError(error));
        });
        dependencies.boot.clearBootState();
        if (dependencies.auth.isAuthenticated) {
            void dependencies.streamManager.resources.startAuto().catch((error) => {
                if (isAbortError(error) || isLifecycleCancellationError(error)) {
                    return;
                }
                errorHandler.warn('AppLifecycle', 'Post-bootstrap auto-resource initialization failed', ensureError(error));
            });
        }
    } catch (error) {
        const runtimeError = ensureError(error);
        const cleanupResult = await cleanupFailedBootstrap({
            navigationBootstrapUnsubscribe: options.navigationBootstrapUnsubscribe,
            connectionSubscription: options.connectionSubscription,
            dataHubConnectionSubscription: options.dataHubConnectionSubscription,
            routerWarmupUnsubscribe: options.routerWarmupUnsubscribe,
            uiTracker: options.uiTracker,
            releaseAuthHandlers: options.releaseAuthHandlers,
            clearSoaiOsAccess: () => dependencies.soaiOsCapabilities.clearAccess(),
            resetConnectionStatus: () => dependencies.connectionStatus.reset(),
            resetMainStatusMonitor: () => dependencies.mainStatusMonitor.reset(),
            resetStreamManager: () => dependencies.streamManager.reset(),
            resetBackgroundTasks: () => {
                if (dependencies.backgroundTasks.reset) {
                    dependencies.backgroundTasks.reset();
                }
            },
            destroyRegisteredComponents: options.destroyRegisteredComponents,
            destroyRouter: () => dependencies.router.destroy(),
            setStateUninitialized: options.setStateUninitialized,
            resetUiBoundState: options.resetUiBoundState,
            clearBootstrapPromise: options.clearBootstrapPromise,
            toggleMainUI: options.toggleMainUI
        });
        options.setNavigationBootstrapUnsubscribe(cleanupResult.navigationBootstrapUnsubscribe);
        options.setConnectionSubscription(cleanupResult.connectionSubscription);
        options.setDataHubConnectionSubscription(cleanupResult.dataHubConnectionSubscription);
        options.setRouterWarmupUnsubscribe(cleanupResult.routerWarmupUnsubscribe);
        options.setUiTracker(cleanupResult.uiTracker);
        options.renderInitializationError(runtimeError);
        throw runtimeError;
    }
};

export { runAppLifecycleBootstrap };
