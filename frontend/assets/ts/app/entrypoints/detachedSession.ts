/* SoAI - Detached authenticated page mounting and lifetime [frontend/assets/ts/app/entrypoints/detachedSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { finalizePreloader } from '@app/bootstrap/bootstrap.ts';
import { initializeAuthenticatedSessionServices, resetAuthenticatedSessionServices } from '@app/bootstrap/stages/sessionServices.ts';
import { runInitializationStage } from '@app/bootstrap/stages/initializationStage.ts';
import { renderDetachedError } from '@app/entrypoints/actions.ts';
import { getAuthManager } from '@core/auth/public.ts';
import { clearDetachedWindowContextForWindow, getDetachedWindowContextForWindow } from '@core/detachedContext.ts';
import { getEventHub } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { createAbortError, isAbortError, raceWithAbortSignal } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { hasNavigationLossProtection, registerBeforeUnloadPrompt } from '@core/navigationGuards.ts';
import { LifecycleScope } from '@core/lifecycle/lifecycleScope.ts';
import { isPageContentAvailable, setPageContentAvailable } from '@core/layout/pageContentInteractivity.ts';
import { isPersistedPageHideEvent } from '@core/lifecycle/pageTermination.ts';
import { PageHost } from '@core/pagehost/service.ts';
import { getPageRegistry } from '@core/pageRegistry.ts';
import { revealMountedPageSection } from '@core/pageTransitions.ts';
import { getStreamManager } from '@core/realtime/streammanager/public.ts';
import { ensureStreamManagerReady } from '@core/realtime/streammanager/readiness.ts';
import { getWindowService } from '@core/runtimeenv/public.ts';
import { createPageMountScope } from '@core/routing/pages/basepagecore/pageMountScope.ts';
import { requireRouter } from '@core/routing/router/routerRuntime.ts';
import { StandaloneRoute } from '@core/routing/router/standaloneRoute.ts';
import { normalizeNavigationRequest } from '@core/routing/router/navigationRequest.ts';
import { getRouteDefinitions } from '@core/routeregistry/service.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { destroyWebSocketClient } from '@core/websocketclient/service.ts';

interface DetachedSessionOptions {
    pageId: string;
    windowId: string;
    parameters: JsonObject;
    container: HTMLElement;
}

const initializeDetachedSession = async ({ pageId, windowId, parameters, container }: DetachedSessionOptions): Promise<void> => {
    const detached = getDetachedWindowContextForWindow(windowId);
    const manager = getStreamManager();
    const pageHost = new PageHost({ container, registry: getPageRegistry() });
    const finalParameters: JsonObject = { ...parameters, windowId, detached: true };
    const auth = getAuthManager();
    const mounts = new LifecycleScope();
    let authTransition: Promise<void> = Promise.resolve();
    let activeEpoch: number | null = null;
    let bootstrapping = true;
    let deferredLoginEpoch: number | null = null;
    let cleanupFailure: Error | null = null;
    let terminated = false;
    const presentationListeners = new Set<() => void>();
    const routeDefinition = getRouteDefinitions().find((route) => route.component === pageId);
    if (!routeDefinition) throw new Error(`Detached page ${pageId} has no registered route`);
    const routeParameters: Record<string, string> = {};
    for (const [key, value] of Object.entries(parameters)) if (typeof value === 'string') routeParameters[key] = value;
    const initialRoute = normalizeNavigationRequest(routeDefinition.path, { parameters: routeParameters }).path;
    const routeOwner: StandaloneRoute = new StandaloneRoute({
        component: pageId,
        initialRoute,
        parseRoute: (path) => requireRouter().parseRoute(path),
        renderRoute: (path): Promise<void> => {
            const epoch = auth.authEpoch;
            return enqueue(() => mountPage(epoch, path, true));
        },
        reportFailure: (error) => errorHandler.error('Detached', 'Detached page navigation failed', error)
    });

    const enqueue = (task: () => Promise<void>): Promise<void> => {
        authTransition = authTransition.then(task, task);
        return authTransition;
    };
    const observeTransition = (task: Promise<void>): void => {
        void task.catch((error) => {
            if (!isAbortError(error)) errorHandler.error('Detached', 'Detached session transition failed', ensureError(error));
        });
    };
    const isEpochCurrent = (epoch: number): boolean => !terminated && auth.authEpoch === epoch && auth.isAuthenticated;
    const retirePage = async (stage: string): Promise<void> => {
        try {
            await pageHost.destroyCurrent({ reason: stage });
            manager.reset();
            destroyWebSocketClient();
            await resetAuthenticatedSessionServices();
            if (!terminated) detached.set({ pageId, windowId, parameters: finalParameters, host: null, instance: null, stage });
        } catch (error) {
            cleanupFailure = ensureError(error);
            throw cleanupFailure;
        }
    };
    const invalidate = (): void => {
        setPageContentAvailable(container, false);
        for (const listener of [...presentationListeners]) listener();
        const retiringEpoch = activeEpoch;
        activeEpoch = null;
        mounts.abort('authentication-changed');
        pageHost.cancelPrepared('authentication-changed');
        const current = pageHost.getCurrent();
        if (current) pageHost.cancelCurrent(current.instance, 'authentication-changed');
        if (retiringEpoch !== null) observeTransition(enqueue(() => retirePage('auth-required')));
    };
    const mountPage = async (epoch: number, candidateRoute = routeOwner.currentRoute, force = false): Promise<void> => {
        if (!isEpochCurrent(epoch)) throw createAbortError();
        if (cleanupFailure) throw cleanupFailure;
        if (!force && activeEpoch === epoch && pageHost.getCurrent()) return;
        const run = mounts.begin('mount');
        activeEpoch = epoch;
        const requireCurrent = (): void => {
            if (!mounts.isCurrent(run) || !isEpochCurrent(epoch)) throw createAbortError();
        };
        const wait = async (task: Promise<void>): Promise<void> => {
            await raceWithAbortSignal(task, run.signal);
            requireCurrent();
        };
        requireCurrent();
        getWindowService().confirmDetachedContextOwner(auth.user?.id ?? null);
        requireCurrent();
        await runInitializationStage('session', async () => {
            await wait(initializeAuthenticatedSessionServices());
            await wait(ensureStreamManagerReady(manager.resources, { allowDiscovery: true }));
        });
        requireCurrent();
        detached.set({ pageId, windowId, parameters: finalParameters, host: null, instance: null, stage: 'stream-ready' });
        requireCurrent();
        detached.set({ pageId, windowId, parameters: finalParameters, host: pageHost, instance: null, stage: 'mounting' });
        await runInitializationStage('routeRendering', async () => {
            requireCurrent();
            const parsed = routeOwner.routing.parseRoute(candidateRoute);
            if (!parsed || parsed.route.component !== pageId) throw new Error('Detached page route does not match its component');
            await raceWithAbortSignal(
                pageHost.prepare(
                    pageId,
                    { ...finalParameters, ...parsed.parameters },
                    {
                        signal: run.signal,
                        createMountScope: (binding) =>
                            createPageMountScope({
                                type: 'standalone',
                                ownerId: windowId,
                                candidateRoute,
                                authEpoch: epoch,
                                readAuthEpoch: () => auth.authEpoch,
                                binding,
                                routing: routeOwner.routing,
                                presentation: {
                                    isVisible: () => isPageContentAvailable(container),
                                    isFocused: () => true,
                                    subscribe: (listener) => {
                                        presentationListeners.add(listener);
                                        return () => {
                                            presentationListeners.delete(listener);
                                        };
                                    }
                                }
                            })
                    }
                ),
                run.signal
            );
            requireCurrent();
            const previousRoute = routeOwner.currentRoute;
            const instance = await pageHost.commitPrepared({
                signal: run.signal,
                finalAdmission: requireCurrent,
                mountPublication: {
                    commit: () => {
                        routeOwner.currentRoute = candidateRoute;
                    },
                    rollback: () => {
                        routeOwner.currentRoute = previousRoute;
                    }
                }
            });
            requireCurrent();
            if (!instance) throw new Error(`Detached page ${pageId} lost mount ownership`);
            detached.set({ instance, host: pageHost, pageId, windowId, parameters: finalParameters, stage: 'mounted' });
            await wait(pageHost.whenReady({ waitForReveal: false }));
            setPageContentAvailable(container, true);
            for (const listener of [...presentationListeners]) listener();
            revealMountedPageSection(container);
            requireCurrent();
            pageHost.allowReveal();
            await wait(pageHost.whenReady({ waitForData: true }));
            await wait(finalizePreloader());
            detached.set({ instance, host: pageHost, pageId, windowId, parameters: finalParameters, stage: 'ready' });
        });
    };
    const unsubscribeIntent = auth.onEpochIntent((intent) => {
        invalidate();
        if (intent.type === 'terminal') getWindowService().suspendDetachedContextOwner();
    });
    const unsubscribeLogin = auth.onLogin(() => {
        const epoch = auth.authEpoch;
        if (bootstrapping) deferredLoginEpoch = epoch;
        else observeTransition(enqueue(() => mountPage(epoch)));
    });
    const unsubscribeLogout = auth.onLogout(() => {
        const epoch = auth.authEpoch;
        observeTransition(
            enqueue(async () => {
                if (terminated || auth.authEpoch !== epoch || auth.isAuthenticated) return;
                renderDetachedError(i18n.t('app.detachedWindow.errors.sessionEnded'));
                await finalizePreloader();
            })
        );
    });
    const releaseUnloadPrompt = registerBeforeUnloadPrompt({ scope: getEventHub(), hasUnsavedChanges: hasNavigationLossProtection, getMessage: () => i18n.t('settings.unsavedChanges') });
    const releaseSubscriptions = (): void => {
        releaseUnloadPrompt();
        unsubscribeIntent();
        unsubscribeLogin();
        unsubscribeLogout();
        presentationListeners.clear();
        getEventHub().removeEventListener('pagehide', handleTermination);
    };
    const handleTermination = (event: Event): void => {
        if (isPersistedPageHideEvent(event) || terminated) return;
        terminated = true;
        releaseSubscriptions();
        invalidate();
        clearDetachedWindowContextForWindow(windowId);
    };
    getEventHub().addEventListener('pagehide', handleTermination, { passive: true });
    try {
        await enqueue(async () => {
            if (!auth.isAuthenticated) {
                const authentication = auth.initialize({ wizardState: auth.getWizardStatusSnapshot() });
                const epoch = auth.authEpoch;
                const run = mounts.begin('authentication');
                const result = await runInitializationStage('authentication', () => raceWithAbortSignal(authentication, run.signal));
                if (!mounts.isCurrent(run) || auth.authEpoch !== epoch || terminated) throw createAbortError();
                if (result !== true || !auth.isAuthenticated) throw new Error('Detached window requires an authenticated session');
            }
            await mountPage(auth.authEpoch);
        });
    } catch (error) {
        if (!isAbortError(error) || (activeEpoch !== null && !terminated)) {
            terminated = true;
            releaseSubscriptions();
            invalidate();
            try {
                await authTransition;
            } catch (cleanupError) {
                throw new AggregateError([ensureError(error), ensureError(cleanupError)], 'Detached initialization and cleanup failed');
            }
            throw ensureError(error);
        }
    } finally {
        bootstrapping = false;
        const deferred = deferredLoginEpoch;
        deferredLoginEpoch = null;
        if (deferred !== null && isEpochCurrent(deferred) && activeEpoch !== deferred) observeTransition(enqueue(() => mountPage(deferred)));
    }
};

export { initializeDetachedSession };
