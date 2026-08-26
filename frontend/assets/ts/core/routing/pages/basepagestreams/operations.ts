/* SoAI - Shared routing operations [frontend/assets/ts/core/routing/pages/basepagestreams/operations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { err } from '@core/routing/pages/basepagecore/actions.ts';
import { isEnsureReadyStreamManager, isOperationsSubscriptionManager, isVerifiableSubscriptionManager } from '@core/routing/pages/basepagestreams/mappers.ts';
import type { StreamResourceLoader } from '@core/realtime/streammanager/resourceLoader.ts';
import type { StreamTaskRuntime } from '@core/realtime/streammanager/actions/service.ts';
import type { OperationEvent } from '@core/realtime/streammanager/types.ts';
import type { SubscriptionManager } from '@core/routing/pages/pagetypes/public.ts';
import { isFunction } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';

const ensurePageStreamReady = async (resources: StreamResourceLoader, allowDiscovery = true, signal?: AbortSignal | undefined): Promise<void> => {
    if (!isEnsureReadyStreamManager(resources)) {
        throw err('SM.ensureReady is required');
    }
    const result = resources.ensureReady({ allowDiscovery, signal });
    await Promise.resolve(result);
};

const subscribeToPageOperations = async (resources: StreamResourceLoader, tasks: StreamTaskRuntime, handler: (event: OperationEvent) => void, options: { allowDiscovery?: boolean; track?: boolean } = {}, dependencies: { trackDisposable: (dispose: () => void) => void }): Promise<() => void> => {
    if (typeof handler !== 'function') {
        throw new TypeError('Handler required');
    }
    await ensurePageStreamReady(resources, options.allowDiscovery !== false);
    if (!isOperationsSubscriptionManager(tasks)) {
        throw err('SM.subscribeOperations is required');
    }
    const disposer = tasks.subscribeOperations((eventObject: OperationEvent) => {
        try {
            handler(eventObject);
        } catch (payloadConstructor) {
            const runtimeError = ensureError(payloadConstructor);
            errorHandler.debug('BasePage', 'Operations subscription handler failed', runtimeError);
        }
    });
    if (typeof disposer !== 'function') {
        throw err('SM.subscribeOperations must return a disposer');
    }
    const dispose = (): void => {
        disposer();
    };
    if (options.track !== false) {
        dependencies.trackDisposable(dispose);
    }
    return dispose;
};

const ensurePageDataSubscriptions = async (manager: SubscriptionManager, options: { signal?: AbortSignal } = {}): Promise<void> => {
    if (!isFunction(manager.ensureReady) || !isFunction(manager.getHealthStatus)) {
        throw err('SM support APIs missing');
    }
    const health = manager.getHealthStatus();
    if (!health.length || health.some((item) => !item.active && item.errors < 3)) {
        await manager.ensureReady(options.signal ? { signal: options.signal } : {});
    }
};

const verifyPageSubscriptionsReady = async (manager: SubscriptionManager): Promise<void> => {
    if (!isVerifiableSubscriptionManager(manager)) {
        throw err('SM.verifyReady is required');
    }
    await Promise.resolve(manager.verifyReady());
};

export { ensurePageDataSubscriptions, ensurePageStreamReady, subscribeToPageOperations, verifyPageSubscriptionsReady };
