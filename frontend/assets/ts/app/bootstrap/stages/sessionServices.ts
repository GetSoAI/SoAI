/* SoAI - Frontend application session services [frontend/assets/ts/app/bootstrap/stages/sessionServices.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireAiSetupAttentionLifecycle } from '@core/aisetup/serviceAccess.ts';
import { requireAutomationRunActivityLifecycle } from '@core/automation/serviceAccess.ts';
import { requireChatConversationAttention, requireChatStreamServiceLifecycle } from '@core/chat/streamServiceAccess.ts';
import { hasPluginBackendUpdate } from '@core/plugins/backendUpdates.ts';
import type { StreamResourceLoader } from '@core/realtime/streammanager/resourceLoader.ts';
import { evaluateAutoResourceBannerState } from '@core/routing/pages/basepagestreams/mappers.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { CatalogStore } from '@features/catalog/catalogSubscriptionManager.ts';

interface AuthenticatedSessionPresentation {
    resources: Pick<StreamResourceLoader, 'subscribeAutoState'>;
    catalog: Pick<CatalogStore, 'subscribe' | 'isFresh'>;
    updateBackendBadge: (available: boolean) => void;
    notifyOffline: (message: string) => void;
}

let presentation: AuthenticatedSessionPresentation | null = null;
let initialization: Promise<void> | null = null;
let resetTask: Promise<void> | null = null;
let sessionController: AbortController | null = null;
let presentationResources: ResourceTracker | null = null;

const configureAuthenticatedSessionPresentation = (dependencies: AuthenticatedSessionPresentation): void => {
    if (sessionController || resetTask) throw new Error('Authenticated session presentation is already active or awaiting cleanup');
    presentation = dependencies;
};

const initializeAuthenticatedSessionServices = async (): Promise<void> => {
    if (resetTask) await resetTask;
    if (initialization) return await initialization;
    const dependencies = presentation;
    if (!dependencies) throw new Error('Authenticated session presentation is not configured');
    const controller = new AbortController();
    const resources = new ResourceTracker();
    const completion = createDeferred<void>();
    sessionController = controller;
    presentationResources = resources;
    initialization = completion.promise;
    const start = async (): Promise<void> => {
        let offlineVisible = false;
        resources.track(
            dependencies.resources.subscribeAutoState(
                (value) => {
                    if (controller.signal.aborted) return;
                    const result = evaluateAutoResourceBannerState(value, offlineVisible);
                    if (result.shouldShowOfflineBanner && result.message) {
                        offlineVisible = true;
                        dependencies.notifyOffline(result.message);
                    } else if (result.shouldClearOfflineBanner) offlineVisible = false;
                },
                { emitCurrent: true }
            )
        );
        resources.track(
            dependencies.catalog.subscribe(
                (plugins) => {
                    if (!controller.signal.aborted) dependencies.updateBackendBadge(dependencies.catalog.isFresh() && plugins.some(hasPluginBackendUpdate));
                },
                { emitInitial: true }
            )
        );
        if (controller.signal.aborted) return;
        requireChatStreamServiceLifecycle().initialize();
        if (controller.signal.aborted) return;
        await requireChatConversationAttention().initialize();
        if (controller.signal.aborted) return;
        await requireAutomationRunActivityLifecycle().initialize();
        if (controller.signal.aborted) return;
        requireAiSetupAttentionLifecycle().initialize();
    };
    const operation = start().catch(async (error) => {
        if (sessionController === controller) {
            sessionController = null;
            presentationResources = null;
            initialization = null;
        }
        controller.abort();
        try {
            await resources.dispose();
        } catch (cleanupError) {
            throw new AggregateError([ensureError(error), ensureError(cleanupError)], 'Authenticated session presentation setup and cleanup failed');
        }
        throw ensureError(error);
    });
    void operation.then(completion.resolve, (error) => completion.reject(ensureError(error)));
    await completion.promise;
};

const resetAuthenticatedSessionServices = async (): Promise<void> => {
    if (resetTask) return await resetTask;
    const completion = createDeferred<void>();
    resetTask = completion.promise;
    const controller = sessionController;
    const resources = presentationResources;
    sessionController = null;
    presentationResources = null;
    initialization = null;
    const stop = async (): Promise<void> => {
        controller?.abort();
        const failures: Error[] = [];
        const release = async (operation: () => void | Promise<void>): Promise<void> => {
            try {
                await operation();
            } catch (error) {
                failures.push(ensureError(error));
            }
        };
        await Promise.all([
            release(() => resources?.dispose()),
            release(() => requireChatStreamServiceLifecycle().dispose()),
            release(() => requireChatConversationAttention().dispose()),
            release(() => requireAiSetupAttentionLifecycle().dispose()),
            release(async () => {
                await requireAutomationRunActivityLifecycle().destroy();
            })
        ]);
        if (failures.length) {
            presentationResources = resources;
            throw new AggregateError(failures, 'Authenticated session cleanup incomplete');
        }
        if (resetTask === completion.promise) resetTask = null;
    };
    void stop().then(completion.resolve, (error) => completion.reject(ensureError(error)));
    await completion.promise;
};

export { configureAuthenticatedSessionPresentation, initializeAuthenticatedSessionServices, resetAuthenticatedSessionServices };
export type { AuthenticatedSessionPresentation };
