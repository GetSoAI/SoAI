/* SoAI - Frontend application service [frontend/assets/ts/app/entrypoints/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { finalizePreloader } from '@app/bootstrap/bootstrap.ts';
import { renderLifecycleInitializationError } from '@app/bootstrap/stages/applifecycle/dom.ts';
import { clearDetachedWindowContextForWindow, getDetachedWindowContextForWindow } from '@core/detachedContext.ts';
import { getElementByIdStrict, requireDocument } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { registerPageTerminationListeners } from '@core/lifecycle/pageTermination.ts';
import { requireRouter } from '@core/routing/router/routerRuntime.ts';
import { getKernel, getWindowService } from '@core/runtimeenv/public.ts';
import { windowIdentity } from '@core/runtime/windowIdentity.ts';
import { DETACHED_CONTEXT_TIMEOUT_MS } from '@core/runtimeenv/constants.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { isString } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { detachedParameters, ensureCommonIconsPreloaded, ensureEntrypointBootstrapBase, ensureLanguageInitialized, initializeScrollModule, requireAppLifecycle, waitForDomReady, waitForWindowLoad, whenBackendReady } from '@app/entrypoints/actions.ts';
import { initializeDetachedSession } from '@app/entrypoints/detachedSession.ts';
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
    } else {
        router.registerRoutes();
    }
    detached.set({ pageId, windowId, parameters, host: null, instance: null, stage: 'router-ready' });

    await Promise.all([ensureLanguageInitialized(), ensureCommonIconsPreloaded(), backendReadyPromise]);
    detached.set({ pageId, windowId, parameters, host: null, instance: null, stage: 'backend-ready' });

    await initializeDetachedSession({ pageId, windowId, parameters, container: mainContentElement });
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
