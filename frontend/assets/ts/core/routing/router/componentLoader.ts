/* SoAI - Shared routing component loader [frontend/assets/ts/core/routing/router/componentLoader.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError, extractErrorMessage } from '@core/errors/coerce.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { toLowerCase, toTrimmedString } from '@core/normalize.ts';
import { ensureStreamManagerReady } from '@core/realtime/streammanager/readiness.ts';
import type { DomService, ErrorHandlerService, ResourceTrackerInstance, StreamManagerService } from '@core/routing/router/routerDependencies.ts';
import type { NavigationRequest, NavigationTarget, RouteDefinition, RouteParameters } from '@core/routing/router/types.ts';
import { filterTrimmedStringArrayValue } from '@core/types/payloadArrayReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isElementNode, isNullOrUndefined, isString } from '@core/typeGuards.ts';

interface RouterComponentLoaderHost {
    dom: DomService;
    resources: ResourceTrackerInstance;
    streamManager: StreamManagerService;
    errorHandler: ErrorHandlerService;
    emitEvent: (stage: string, data?: Record<string, JsonValue | null | undefined>, severity?: string) => void;
    isComponentRegistered: (name: string) => boolean;
    normalizeNavigationRequest: (target: string | NavigationTarget) => NavigationRequest;
    resolveRouteDetails: (path: string, route: RouteDefinition | null, parameters: RouteParameters | null) => { path: string; route: RouteDefinition; parameters: RouteParameters };
    validateNavigation: (route: RouteDefinition) => void;
}

class RouterComponentLoader {
    #host: RouterComponentLoaderHost;
    #prefetchListenersInitialized = false;
    #preloadTasks: Map<string, Promise<void>> = new Map();

    constructor(host: RouterComponentLoaderHost) {
        this.#host = host;
    }

    async preload(target: string | NavigationTarget): Promise<void> {
        const request = this.#host.normalizeNavigationRequest(target);
        const details = this.#host.resolveRouteDetails(request.path, request.route, request.parameters);
        await this.#preloadRoute(details.route);
    }

    async preloadDependencies(route: RouteDefinition | null = null, signal?: AbortSignal): Promise<void> {
        if (route) this.#warmRouteData(route, signal);
    }

    initializeNavigationPrefetch(): void {
        if (this.#prefetchListenersInitialized) return;
        const doc = this.#host.dom.getDocument();
        this.#host.resources.addEventListener(
            doc,
            'pointerover',
            (event: Event) => {
                if (!this.#allowPointer(event)) return;
                const target = event.target;
                if (!isElementNode(target)) return;
                const navigationTarget = this.#resolvePrefetchTarget(target);
                if (!navigationTarget) {
                    return;
                }
                void this.preload(navigationTarget).catch((error) => {
                    this.#host.errorHandler.debug('Router', 'Prefetch preload failed', {
                        message: extractErrorMessage(error),
                        target: navigationTarget
                    });
                });
            },
            { passive: true }
        );

        this.#prefetchListenersInitialized = true;
    }

    async #preloadRoute(route: RouteDefinition): Promise<void> {
        this.#host.validateNavigation(route);
        const name = route.component;

        const existingTask = this.#preloadTasks.get(name);
        if (existingTask) {
            await existingTask;
            return;
        }

        const baseTask = (async (): Promise<void> => {
            this.#host.emitEvent('component:preload:start', { component: name, route: route.path || null });
            this.#host.emitEvent('component:preload:ready', { component: name, route: route.path || null });
        })().catch((error) => {
            this.#host.emitEvent('component:preload:error', { component: name, route: route.path || null, message: extractErrorMessage(error) }, 'error');
            throw error;
        });

        let guardedTaskRef: Promise<void> | null = null;
        const guardedTask = (async (): Promise<void> => {
            try {
                await baseTask;
            } finally {
                const current = this.#preloadTasks.get(name);
                if (guardedTaskRef && current === guardedTaskRef) this.#preloadTasks.delete(name);
            }
        })();
        guardedTaskRef = guardedTask;

        this.#preloadTasks.set(name, guardedTask);
        await guardedTask;
    }

    #warmRouteData(route: RouteDefinition, signal?: AbortSignal): void {
        const request = route.data;
        if (!request || signal?.aborted) return;

        const targets = Array.from(new Set([...filterTrimmedStringArrayValue(request.streams), ...filterTrimmedStringArrayValue(request.resources)]));
        if (!targets.length) return;

        void ensureStreamManagerReady(this.#host.streamManager, { allowDiscovery: true, signal })
            .then(async () => {
                if (signal?.aborted) return;
                await Promise.all(
                    targets.map(async (name) => {
                        try {
                            await this.#host.streamManager.ensureResourceStarted(name, { signal });
                        } catch (error) {
                            const runtimeError = ensureError(error);
                            if (isAbortError(runtimeError) && signal?.aborted) return;
                            this.#host.errorHandler.warn('Router', `Route data warmup failed for ${name}`, runtimeError);
                        }
                    })
                );
            })
            .catch((error) => {
                const runtimeError = ensureError(error);
                if (isAbortError(runtimeError) && signal?.aborted) return;
                this.#host.errorHandler.warn('Router', 'Route data warmup failed', runtimeError);
            });
    }

    #allowPointer(event: Event): boolean {
        if (!event) return false;
        if (!(typeof PointerEvent === 'function' && event instanceof PointerEvent)) {
            return true;
        }
        const pointerTypeValue = event.pointerType;
        if (isNullOrUndefined(pointerTypeValue)) return true;
        if (!isString(pointerTypeValue)) return false;
        const pointerType = toLowerCase(pointerTypeValue);
        return pointerType === 'mouse' || pointerType === 'pen';
    }

    #resolvePrefetchTarget(target: Element): string | null {
        const navigateElement = target.closest('[data-navigate]');
        if (navigateElement) {
            return this.#readPrefetchAttribute(navigateElement, 'navigate');
        }
        const pageElement = target.closest('.sidebar-link[data-page]');
        if (pageElement) {
            return this.#readPrefetchAttribute(pageElement, 'page');
        }
        return null;
    }

    #readPrefetchAttribute(element: Element, dataAttr: string): string | null {
        const id = element.getAttribute(`data-${dataAttr}`);
        if (!isString(id)) {
            return null;
        }
        const trimmed = toTrimmedString(id);
        return trimmed || null;
    }
}

export { RouterComponentLoader };
export type { RouterComponentLoaderHost };
