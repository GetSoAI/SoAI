/* SoAI - Frontend application service [frontend/assets/ts/app/entrypoints/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { finalizePreloader } from '@app/bootstrap/bootstrap.ts';
import { renderLifecycleInitializationError } from '@app/bootstrap/stages/applifecycle/dom.ts';
import { initializeAuthenticatedSessionServices, resetAuthenticatedSessionServices } from '@app/bootstrap/stages/sessionServices.ts';
import { getAuthManager } from '@core/auth/public.ts';
import { clearDetachedWindowContextForWindow, getDetachedWindowContextForWindow } from '@core/detachedContext.ts';
import { getElementByIdStrict, getEventHub, requireDocument } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { registerPageTerminationListeners } from '@core/lifecycle/pageTermination.ts';
import { PageHost } from '@core/pagehost/service.ts';
import { getPageRegistry } from '@core/pageRegistry.ts';
import { revealMountedPageSection } from '@core/pageTransitions.ts';
import { getStreamManager } from '@core/realtime/streammanager/public.ts';
import { ensureStreamManagerReady } from '@core/realtime/streammanager/readiness.ts';
import { requireRouter } from '@core/routing/router/routerRuntime.ts';
import { getKernel, getWindowService } from '@core/runtimeenv/public.ts';
import { windowIdentity } from '@core/runtime/windowIdentity.ts';
import { DETACHED_CONTEXT_TIMEOUT_MS } from '@core/runtimeenv/constants.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { isString } from '@core/typeGuards.ts';
import { destroyWebSocketClient } from '@core/websocketclient/service.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { detachedParameters, ensureCommonIconsPreloaded, ensureEntrypointBootstrapBase, ensureLanguageInitialized, initializeScrollModule, requireAppLifecycle, renderDetachedError, waitForDomReady, waitForWindowLoad, whenBackendReady } from '@app/entrypoints/actions.ts';
import { setupCleanupHandlers } from '@app/entrypoints/events.ts';
import { reportInitializationFailure, runInitializationStage } from '@app/bootstrap/stages/initializationStage.ts';

const logBootstrapStage = (stage: string, detail: JsonObject | null = null): void => {
    errorHandler.info('Bootstrap', stage, detail, { stage });
};

const prepareEntrypoint = (): Promise<void> =>
    runInitializationStage('entrypoint', async () => {
        await ensureEntrypointBootstrapBase();
        await ensureLanguageInitialized();
    });

const primaryStart = async (): Promise<void> => {
    logBootstrapStage('bootstrap:start');
    await prepareEntrypoint();
    const appLifecycle = await runInitializationStage('criticalServices', async () => {
        const backendReadyPromise = whenBackendReady({ allowDiscovery: true });
        terminateHandledPromise(backendReadyPromise);
        logBootstrapStage('backend:pending');
        logBootstrapStage('kernel:start');

        await getKernel().start();
        logBootstrapStage('kernel:ready');

        await backendReadyPromise;
        logBootstrapStage('backend:ready');

        await getKernel().refresh();
        logBootstrapStage('kernel:refresh');

        const lifecycle = requireAppLifecycle();
        await ensureCommonIconsPreloaded();
        return lifecycle;
    });
    await appLifecycle.bootstrap();

    const router = requireRouter();
    logBootstrapStage('appLifecycle:ready', { route: router.getCurrentRoute?.() ?? null });

    initializeScrollModule();
};

const ensureDetachedAuthentication = async (): Promise<void> => {
    const authManager = getAuthManager();
    if (authManager.isAuthenticated) return;
    let initializationError: Error | null = null;
    let initializationResult: boolean | undefined = undefined;
    try {
        initializationResult = await authManager.initialize({ wizardState: authManager.getWizardStatusSnapshot() });
    } catch (error) {
        const runtimeError = ensureError(error);
        initializationError = runtimeError;
        errorHandler.warn('Detached', 'Auth initialize failed for detached window', runtimeError);
    }
    if (authManager.isAuthenticated) return;
    if (initializationError) throw initializationError;
    if (initializationResult === undefined) {
        throw new Error('Detached window authentication status could not be determined');
    }
    throw new Error('Detached window requires an authenticated session');
};

const initializeDetached = async (pageId: string, windowId: string): Promise<void> => {
    await waitForWindowLoad();
    registerPageTerminationListeners();
    clearDetachedWindowContextForWindow(windowId);
    const detached = getDetachedWindowContextForWindow(windowId);
    if (!isString(pageId) || !pageId.trim()) throw new Error('Detached window requires a valid page identifier');

    detached.set({ pageId, windowId, parameters: {}, host: null, instance: null, stage: 'modules-ready' });

    await getWindowService().awaitDetachedContext({ timeout: DETACHED_CONTEXT_TIMEOUT_MS });
    const metadata = getWindowService().getDetachedMetadata();
    if (!metadata) {
        throw new Error('Detached window context did not provide metadata');
    }
    if (metadata.pageId && metadata.pageId !== pageId) {
        throw new Error('Detached window metadata pageId mismatch');
    }
    const parameters = metadata.parameters;

    detached.set({ pageId, windowId, parameters, host: null, instance: null, stage: 'context-ready' });

    const backendReadyPromise = whenBackendReady({ allowDiscovery: true });
    terminateHandledPromise(backendReadyPromise);
    await getKernel().start();
    detached.set({ pageId, windowId, parameters, host: null, instance: null, stage: 'kernel-started' });

    const mainContentElement = getElementByIdStrict('main-content');
    const router = requireRouter();
    if (!windowIdentity.isDetachedContext()) {
        if (!router.contentContainer) router.initialize(mainContentElement);
        else if (router.contentContainer !== mainContentElement) router.setContentContainer(mainContentElement);
    }
    detached.set({ pageId, windowId, parameters, host: null, instance: null, stage: 'router-ready' });

    await Promise.all([ensureLanguageInitialized(), ensureCommonIconsPreloaded(), backendReadyPromise]);
    detached.set({ pageId, windowId, parameters, host: null, instance: null, stage: 'backend-ready' });

    const manager = getStreamManager();
    const streamResources = manager.resources;
    const pageHost = new PageHost({ container: mainContentElement, registry: getPageRegistry() });
    const finalParameters: JsonObject = { ...parameters, windowId, detached: true };
    const authManager = getAuthManager();
    let authTransition: Promise<void> = Promise.resolve();

    const destroyPage = async (stage: string): Promise<void> => {
        await pageHost.destroyCurrent({ force: true });
        detached.set({ pageId, windowId, parameters: finalParameters, host: null, instance: null, stage });
    };

    const resetSessionState = async (): Promise<void> => {
        manager.reset();
        destroyWebSocketClient();
        await resetAuthenticatedSessionServices();
    };

    const mountPage = async (): Promise<void> => {
        await runInitializationStage('authentication', ensureDetachedAuthentication);
        getWindowService().confirmDetachedContextOwner(authManager.user?.id ?? null);
        await runInitializationStage('session', async () => {
            await initializeAuthenticatedSessionServices();
            await ensureStreamManagerReady(streamResources, { allowDiscovery: true });
        });
        detached.set({ pageId, windowId, parameters: finalParameters, host: null, instance: null, stage: 'stream-ready' });
        detached.set({ pageId, windowId, parameters: finalParameters, host: pageHost, instance: null, stage: 'mounting' });
        const instance = await runInitializationStage('routeRendering', async () => {
            await pageHost.prepare(pageId, finalParameters);
            const committed = await pageHost.commitPrepared();
            if (!committed) throw new Error(`Detached page ${pageId} lost mount ownership`);
            detached.set({ instance: committed, host: pageHost, pageId, windowId, parameters: finalParameters, stage: 'mounted' });
            await pageHost.whenReady({ waitForReveal: false });
            revealMountedPageSection(mainContentElement);
            pageHost.allowReveal();
            await pageHost.whenReady({ waitForData: true });
            return committed;
        });
        await finalizePreloader().catch((error) => {
            errorHandler.warn('Detached', 'Preloader finalization failed after detached mount', ensureError(error));
        });
        detached.set({ instance, host: pageHost, pageId, windowId, parameters: finalParameters, stage: 'ready' });
    };

    const enqueueAuthTransition = (task: () => Promise<void>): Promise<void> => {
        authTransition = authTransition.then(task, task);
        return authTransition;
    };

    try {
        await mountPage();
    } catch (error) {
        const runtimeError = ensureError(error);
        try {
            await destroyPage('failed');
            await resetSessionState();
        } catch (cleanupError) {
            reportInitializationFailure('Detached', 'Detached initialization cleanup failed', runtimeError, ensureError(cleanupError));
        }
        throw runtimeError;
    }

    const unsubscribeLogin = authManager.onLogin(() => {
        void enqueueAuthTransition(async () => {
            if (pageHost.getCurrent()) return;
            await mountPage();
        }).catch((error) => {
            errorHandler.error('Detached', 'Detached login transition failed', ensureError(error));
        });
    });

    const unsubscribeLogout = authManager.onLogout(() => {
        getWindowService().suspendDetachedContextOwner();
        void enqueueAuthTransition(async () => {
            await destroyPage('auth-required');
            await resetSessionState();
            renderDetachedError(i18n.t('app.detachedWindow.errors.sessionEnded'));
        }).catch((error) => {
            errorHandler.error('Detached', 'Detached logout transition failed', ensureError(error));
        });
    });

    getEventHub().addEventListener(
        'beforeunload',
        () => {
            unsubscribeLogin();
            unsubscribeLogout();
            void pageHost.destroyCurrent({ force: true }).catch((error) => {
                errorHandler.warn('Detached', 'Detached page cleanup failed during beforeunload', error);
            });
            const currentContext = detached.get();
            const contextWindowId = currentContext ? currentContext.windowId : null;
            if (contextWindowId === windowId) {
                clearDetachedWindowContextForWindow(windowId);
            }
        },
        { passive: true }
    );
};

let primaryPromise: Promise<void> | null = null;
let detachedPromise: Promise<void> | null = null;

const startPrimaryApp = (): Promise<void> => {
    if (!primaryPromise) {
        const runPrimaryStart = async (): Promise<void> => {
            await waitForDomReady();
            const disposePageTermination = registerPageTerminationListeners();
            try {
                await primaryStart();
                setupCleanupHandlers();
            } catch (error) {
                disposePageTermination();
                const runtimeError = ensureError(error);
                reportInitializationFailure('Main', 'Application bootstrap failed', runtimeError);
                renderLifecycleInitializationError(runtimeError, () => finalizePreloader());
                throw runtimeError;
            }
        };
        primaryPromise = runPrimaryStart().catch((error) => {
            primaryPromise = null;
            throw ensureError(error);
        });
    }
    return primaryPromise;
};

const startDetachedWindow = (): Promise<void> => {
    if (!detachedPromise) {
        const runDetachedInitialization = async (): Promise<void> => {
            let missingPage = false;
            const windowId = windowIdentity.current();
            await waitForDomReady();
            try {
                await prepareEntrypoint();
                const { pageId } = detachedParameters();
                const doc = requireDocument();
                if (!isString(pageId) || !pageId.trim()) {
                    doc.title = i18n.t('app.detachedWindow.defaultTitle');
                    missingPage = true;
                    throw new Error('Detached window requires a page identifier');
                }
                const normalizedPageId = pageId.trim();
                const capitalizedPageId = normalizedPageId.charAt(0).toUpperCase() + normalizedPageId.slice(1);
                doc.title = i18n.t('app.detachedWindow.pageTitle', { page: capitalizedPageId });
                await runInitializationStage('criticalServices', () => initializeDetached(normalizedPageId, windowId));
            } catch (error) {
                const runtimeError = ensureError(error);
                reportInitializationFailure('Detached', 'Failed to initialize detached page', runtimeError);
                clearDetachedWindowContextForWindow(windowId);
                renderLifecycleInitializationError(runtimeError, () => finalizePreloader(), { surface: 'detached', missingPage });
                throw runtimeError;
            }
        };
        detachedPromise = runDetachedInitialization().catch((error) => {
            detachedPromise = null;
            throw ensureError(error);
        });
    }
    return detachedPromise;
};

export { startDetachedWindow, startPrimaryApp };
