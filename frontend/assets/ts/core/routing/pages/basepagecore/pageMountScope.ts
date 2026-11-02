/* SoAI - Immutable page mount route projection and mutation admission [frontend/assets/ts/core/routing/pages/basepagecore/pageMountScope.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CleanupStack } from '@core/lifecycle/cleanupStack.ts';
import { runCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';
import { isLifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import { createAbortError } from '@core/errors/abort.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { getQueryParametersFromHash } from '@core/routing/router/queryParameters.ts';
import type { PageMountBinding, PageMountPresentation, PageMountScope, PageRouting } from '@core/routing/router/types.ts';

interface PageMountScopeOptions {
    type: PageMountScope['type'];
    ownerId: string;
    candidateRoute: string;
    authEpoch: number;
    readAuthEpoch: () => number;
    binding: PageMountBinding;
    routing: PageRouting;
    presentation: PageMountPresentation;
}

const createPageMountScope = ({ type, ownerId, candidateRoute, authEpoch, readAuthEpoch, binding, routing, presentation }: PageMountScopeOptions): PageMountScope => {
    if (!ownerId || !candidateRoute) throw new Error('Page mounts require an owner and candidate route');
    const mutationBarriers = new Set<symbol>();
    const isCurrent = (): boolean => readAuthEpoch() === authEpoch && binding.isCurrent();
    const requireActive = (): void => {
        if (!isCurrent() || !binding.isActive()) throw createAbortError('Page mount is not active');
    };
    const getCurrentRoute = (): string => (binding.isCommitted() ? (routing.getCurrentRoute() ?? candidateRoute) : candidateRoute);
    const scopedRouting = Object.freeze<PageRouting>({
        back: () => {
            requireActive();
            routing.back();
        },
        navigate: async (target, options) => {
            requireActive();
            await routing.navigate(target, options);
        },
        navigateWithQuery: (path, query, options) => {
            requireActive();
            routing.navigateWithQuery(path, query, options);
        },
        reload: async () => {
            requireActive();
            await routing.reload();
        },
        replaceCurrentRoute: (target) => {
            requireActive();
            routing.replaceCurrentRoute(target);
        },
        getCurrentRoute,
        getRouteParameters: () => {
            const route = getCurrentRoute();
            const resolved = routing.parseRoute(route);
            if (!resolved) throw new Error(`Page mount cannot parse route: ${route}`);
            return resolved.parameters;
        },
        getQueryParameters: () => getQueryParametersFromHash(`#${getCurrentRoute()}`),
        parseRoute: (path) => routing.parseRoute(path),
        getDefaultRoute: () => routing.getDefaultRoute()
    });
    return Object.freeze({
        type,
        ownerId,
        generation: binding.generation,
        candidateRoute,
        authEpoch,
        routing: scopedRouting,
        presentation: Object.freeze({
            isVisible: () => isCurrent() && binding.isActive() && presentation.isVisible(),
            isFocused: () => isCurrent() && binding.isActive() && presentation.isVisible() && presentation.isFocused(),
            subscribe: (listener: () => void) => {
                if (!isCurrent()) throw createAbortError('Page mount is no longer current');
                let closed = false;
                let subscribing = false;
                let paneAttached = false;
                const cleanup = new CleanupStack({ logError: (message, error) => errorHandler.debug('PageMountScope', message, error) });
                const dispose = (): void => {
                    closed = true;
                    throwCollectedCleanupFailures(cleanup.dispose());
                };
                const notify = (): void => {
                    try {
                        listener();
                    } catch (error) {
                        errorHandler.error('PageMountScope', 'Page presentation observer failed', ensureError(error));
                    }
                };
                const synchronize = (): void => {
                    if (closed) return;
                    if (!isCurrent()) dispose();
                    else if (binding.isActive()) attachPane();
                    notify();
                };
                const attachPane = (): void => {
                    if (closed || subscribing || paneAttached) return;
                    subscribing = true;
                    try {
                        const unsubscribe = presentation.subscribe(synchronize);
                        cleanup.add(unsubscribe);
                        paneAttached = !closed;
                        if (!isCurrent()) dispose();
                    } catch (error) {
                        if (!closed || !isLifecycleCancellationError(error)) throw error;
                        throwCollectedCleanupFailures(cleanup.dispose());
                    } finally {
                        subscribing = false;
                    }
                };
                try {
                    cleanup.add(binding.subscribe(synchronize));
                    if (!isCurrent()) dispose();
                    else if (binding.isActive()) attachPane();
                } catch (error) {
                    const failures: Error[] = closed && isLifecycleCancellationError(error) ? [] : [ensureError(error)];
                    runCleanupStepCollectingFailure(dispose, failures);
                    throwCollectedCleanupFailures([...new Set(failures)]);
                }
                return dispose;
            }
        }),
        admission: Object.freeze({
            isCurrent,
            isActive: () => isCurrent() && binding.isActive(),
            canMutate: () => isCurrent() && binding.isActive() && mutationBarriers.size === 0,
            blockMutations: () => {
                const barrier = Symbol('page-mutation-admission');
                mutationBarriers.add(barrier);
                return () => {
                    mutationBarriers.delete(barrier);
                };
            },
            requireActive
        })
    });
};

export { createPageMountScope };
export type { PageMountScopeOptions };
