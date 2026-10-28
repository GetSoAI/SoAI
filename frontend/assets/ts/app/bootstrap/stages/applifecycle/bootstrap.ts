/* SoAI - Frontend application lifecycle bootstrap [frontend/assets/ts/app/bootstrap/stages/applifecycle/bootstrap.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { cleanupFailedBootstrap, type LifecycleBootstrapResources } from '@app/bootstrap/stages/applifecycle/actions.ts';
import { prepareLifecycleEnvironment } from '@app/bootstrap/stages/applifecycle/dom.ts';
import { ensureLifecycleCriticalServicesReady, navigateLifecycleRoute, prepareLifecycleRefresh, primeLifecycleBackendDiscovery } from '@app/bootstrap/stages/applifecycle/effects.ts';
import { ensureBootstrapRouteRendered } from '@app/bootstrap/stages/applifecycle/routing.ts';
import type { AppLifecycleDependencies, LifecycleBackgroundOptions, LifecycleRoute } from '@app/bootstrap/stages/applifecycle/types.ts';
import { isIntentionalInitializationCancellation, reportInitializationFailure, runInitializationStage } from '@app/bootstrap/stages/initializationStage.ts';
import { getElementByIdStrict } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { onNavigationComplete } from '@core/navigationEvents.ts';
import { resetSaveHeaderActionState } from '@core/save/public.ts';
import { isObject, isString } from '@core/typeGuards.ts';

interface RunAppLifecycleBootstrapOptions {
    dependencies: AppLifecycleDependencies;
    isRefreshScenario: boolean;
    navigationBootstrapUnsubscribe: (() => void) | null;
    takeResources: () => LifecycleBootstrapResources;
    setNavigationBootstrapUnsubscribe: (value: (() => void) | null) => void;
    setStateUninitialized: () => void;
    resetUiBoundState: () => void;
    clearBootstrapPromise: () => void;
    registerAuthHandlers: () => void;
    releaseAuthHandlers: () => void;
    refreshSoaiOsAccess: () => Promise<void>;
    resolveInitialRoute: (isAuthenticated: boolean, needsWizard: boolean) => string;
    setupAuthenticatedSession: (options: { force?: boolean; initialRoute?: string | null }) => Promise<void>;
    applyBackground: (route: LifecycleRoute, options?: LifecycleBackgroundOptions) => Promise<void>;
    monitorConnectionStatus: () => void;
    toggleMainUI: (show: boolean) => void;
    destroyRegisteredComponents: () => Promise<void>;
}

const runAppLifecycleBootstrap = async (options: RunAppLifecycleBootstrapOptions): Promise<boolean> => {
    const { dependencies } = options;
    dependencies.router.setBrowserNavigationSuspended(true);
    try {
        await runInitializationStage('criticalServices', async () => {
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
        });
        const { isAuthenticated, needsWizard, warmupRoute } = await runInitializationStage('authentication', async () => {
            const needsWizard = (await dependencies.auth.checkWizardStatus()) === true;
            const wizardStatus = dependencies.auth.getWizardStatusSnapshot();
            await dependencies.auth.initialize({ wizardState: wizardStatus ?? null, skipSessionProbe: needsWizard });
            options.registerAuthHandlers();
            const authenticated = dependencies.auth.isAuthenticated;
            if (authenticated) {
                await options.refreshSoaiOsAccess();
            } else {
                dependencies.soaiOsCapabilities.clearAccess();
            }
            options.toggleMainUI(authenticated);
            return { isAuthenticated: authenticated, needsWizard, warmupRoute: options.resolveInitialRoute(authenticated, needsWizard) };
        });
        if (isAuthenticated) {
            await runInitializationStage('session', () => options.setupAuthenticatedSession({ force: options.isRefreshScenario, initialRoute: warmupRoute }));
        }
        const renderedRoute = await runInitializationStage('routeRendering', async () => {
            const finalRoute = options.resolveInitialRoute(isAuthenticated, needsWizard);
            if (!finalRoute) {
                throw new Error('Route skeleton rendering requires a non-empty route identifier');
            }
            dependencies.router.getPageOutlet().setSkeleton(finalRoute);
            dependencies.router.setBrowserNavigationSuspended(false);
            const initialNavigation = navigateLifecycleRoute(dependencies.router, finalRoute);
            const initialCompletion = dependencies.router.getLatestNavigationCompletion();
            try {
                await initialNavigation;
            } catch (error) {
                const latestCompletion = dependencies.router.getLatestNavigationCompletion();
                if (!latestCompletion || initialCompletion === latestCompletion) throw error;
            }
            return ensureBootstrapRouteRendered(dependencies.router);
        });
        await runInitializationStage('background', async () => {
            await options.applyBackground(renderedRoute);
            const currentRoute = await ensureBootstrapRouteRendered(dependencies.router);
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
            dependencies.backgroundTasks.applyForRoute(currentRoute);
            options.monitorConnectionStatus();
            const preloaderFinalization = dependencies.boot.finalizePreloader();
            dependencies.boot.clearBootState();
            await preloaderFinalization.catch((error) => {
                errorHandler.warn('AppLifecycle', 'Preloader finalization failed after bootstrap', ensureError(error));
            });
        });
        if (dependencies.auth.isAuthenticated) {
            void dependencies.streamManager.resources.startAuto().catch((error) => {
                if (isIntentionalInitializationCancellation(error)) {
                    return;
                }
                errorHandler.warn('AppLifecycle', 'Post-bootstrap auto-resource initialization failed', ensureError(error));
            });
        }
        return isAuthenticated;
    } catch (error) {
        dependencies.router.setBrowserNavigationSuspended(true);
        const runtimeError = ensureError(error);
        try {
            await cleanupFailedBootstrap({
                ...options.takeResources(),
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
        } catch (cleanupError) {
            reportInitializationFailure('AppLifecycle', 'Bootstrap failure cleanup failed', runtimeError, ensureError(cleanupError));
        }
        throw runtimeError;
    }
};

export { runAppLifecycleBootstrap };
