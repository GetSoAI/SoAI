/* SoAI - Pane-local route and navigation ownership [frontend/assets/ts/core/routing/router/RoutePane.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createAbortError, isAbortError, throwIfAborted } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import type { RouterLocalizationRefreshController } from '@core/routing/router/localizationRefresh.ts';
import type { PageOutletService } from '@core/pageoutlet/types.ts';
import type { NavigationRequest, NavigationTarget, RouteDefinition, RouteParameters, PageMountPresentation, PageRouting } from '@core/routing/router/types.ts';

import { buildQueryRoute, getQueryParametersFromHash } from '@core/routing/router/queryParameters.ts';
import { normalizeNavigationRequest } from '@core/routing/router/navigationRequest.ts';
import { resolveRouteTitle } from '@core/routing/router/navigation.ts';
import { runCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';

interface RoutePaneDependencies {
    id: string;
    createResources: (pane: RoutePane) => { outlet: PageOutletService; localization: RouterLocalizationRefreshController; onNavigationSettled(): void };
    executeNavigation: (request: NavigationRequest, signal: AbortSignal, pane: RoutePane) => Promise<void>;
    parseRoute: PageRouting['parseRoute'];
    getDefaultRoute: PageRouting['getDefaultRoute'];
    back: PageRouting['back'];
    resolveTarget: (target: string | NavigationTarget) => { path: string; route: RouteDefinition; parameters: RouteParameters };
    replaceProjection: (path: string, title: string, previousRoute: string, pane: RoutePane) => void;
    reportFailure: (error: Error) => void;
    captureFocusIntent?: ((request: NavigationRequest, pane: RoutePane) => number | null) | undefined;
}

interface RoutePaneNavigation {
    owner: RoutePaneNavigationOwner;
    readonly request: NavigationRequest;
    readonly controller: AbortController;
    readonly completion: Promise<void>;
    focusIntent: number | null;
    committed: boolean;
}

interface RoutePaneNavigationOwner {
    settle(operation: RoutePaneNavigation): void;
    cancel(operation: RoutePaneNavigation | null, reason: string): void;
}

class RoutePane {
    readonly id: string;
    readonly outlet: PageOutletService;
    readonly localization: RouterLocalizationRefreshController;
    readonly #executeNavigation: RoutePaneDependencies['executeNavigation'];
    readonly #onNavigationSettled: () => void;
    readonly #captureFocusIntent: RoutePaneDependencies['captureFocusIntent'];
    readonly routing: PageRouting;
    readonly presentation: PageMountPresentation;
    readonly #presentationListeners = new Set<() => void>();
    #presentationToken = Symbol('pane-presentation');
    #visible = true;
    #focused = true;
    currentRoute: string | null = null;
    #activeNavigation: RoutePaneNavigation | null = null;
    #latestNavigationCompletion: Promise<void> | null = null;
    #retainedNavigation: RoutePaneNavigation | null = null;
    #disposed = false;
    readonly #navigationOwner = Object.freeze<RoutePaneNavigationOwner>({
        settle: (operation) => this.#settleNavigation(operation),
        cancel: (operation, reason) => {
            if (this.#activeNavigation === operation) this.cancel(reason);
        }
    });

    constructor(dependencies: RoutePaneDependencies) {
        this.id = dependencies.id;
        this.#executeNavigation = dependencies.executeNavigation;
        this.#captureFocusIntent = dependencies.captureFocusIntent;
        this.presentation = Object.freeze({
            isVisible: () => this.#visible,
            isFocused: () => this.#focused,
            subscribe: (listener: () => void) => {
                this.#presentationListeners.add(listener);
                return () => {
                    this.#presentationListeners.delete(listener);
                };
            }
        });
        this.routing = Object.freeze<PageRouting>({
            back: () => {
                if (this.#disposed) throw createAbortError('Route pane is disposed');
                dependencies.back();
            },
            navigate: (target, options) => this.navigate(normalizeNavigationRequest(target, options)),
            navigateWithQuery: (path, query, options) => {
                void this.navigate(normalizeNavigationRequest(buildQueryRoute(path, query), options)).catch((error) => dependencies.reportFailure(ensureError(error)));
            },
            reload: async () => {
                if (this.currentRoute) await this.navigate(normalizeNavigationRequest(this.currentRoute, { pushState: false, force: true, presentation: 'background' }));
            },
            getCurrentRoute: () => this.currentRoute,
            getRouteParameters: () => {
                if (!this.currentRoute) throw new Error('Route pane does not have an active route');
                const resolved = dependencies.parseRoute(this.currentRoute);
                if (!resolved) throw new Error(`Router cannot parse current route: ${this.currentRoute}`);
                return resolved.parameters;
            },
            getQueryParameters: () => getQueryParametersFromHash(`#${this.currentRoute ?? ''}`),
            replaceCurrentRoute: (target) => {
                if (this.#disposed) throw createAbortError('Route pane is disposed');
                if (!this.currentRoute) throw new Error('Router cannot replace the current route before a route is active');
                const current = dependencies.parseRoute(this.currentRoute);
                if (!current) throw new Error(`Router cannot parse current route: ${this.currentRoute}`);
                const resolved = dependencies.resolveTarget(target);
                if (current.route.component !== resolved.route.component) throw new Error(`Router cannot replace current route across components: ${current.route.component} -> ${resolved.route.component}`);
                const previousRoute = this.currentRoute;
                this.currentRoute = resolved.path;
                dependencies.replaceProjection(resolved.path, resolveRouteTitle(resolved.route), previousRoute, this);
            },
            parseRoute: dependencies.parseRoute,
            getDefaultRoute: dependencies.getDefaultRoute
        });
        const resources = dependencies.createResources(this);
        this.outlet = resources.outlet;
        this.localization = resources.localization;
        this.#onNavigationSettled = resources.onNavigationSettled;
    }

    readonly navigate = (request: NavigationRequest, capturedFocusIntent?: number | null): Promise<void> => {
        if (this.#disposed) return Promise.reject(createAbortError('Route pane is disposed'));
        const predecessor = this.#activeNavigation;
        const navigation = new AbortController();
        const completion = createDeferred<void>();
        const operation: RoutePaneNavigation = { owner: this.#navigationOwner, request, controller: navigation, completion: completion.promise, focusIntent: null, committed: false };
        if (predecessor?.committed) this.#retainedNavigation = predecessor;
        this.#activeNavigation = operation;
        this.#latestNavigationCompletion = completion.promise;
        let captureFailure: Error | null = null;
        try {
            if (request.presentation !== 'background') operation.focusIntent = capturedFocusIntent !== undefined ? capturedFocusIntent : (this.#captureFocusIntent?.(request, this) ?? null);
        } catch (error) {
            captureFailure = ensureError(error);
        }
        if (!predecessor?.committed) predecessor?.controller.abort('navigation-superseded');
        const execute = async (): Promise<void> => {
            try {
                if (captureFailure) throw captureFailure;
                throwIfAborted(navigation.signal);
                await this.#executeNavigation(request, navigation.signal, this);
            } catch (error) {
                if (!isAbortError(error) || !navigation.signal.aborted) throw error;
            } finally {
                operation.owner.settle(operation);
            }
        };
        void execute().then(completion.resolve, (error) => completion.reject(ensureError(error)));
        return completion.promise;
    };

    getNavigationFocusIntent(signal: AbortSignal): number | null {
        const operation = this.#activeNavigation;
        if (!operation || operation.controller.signal !== signal || signal.aborted) throw createAbortError('Pane navigation no longer owns focus intent');
        return operation.focusIntent;
    }

    transferNavigationTo(destination: RoutePane, signal: AbortSignal): void {
        const operation = this.#activeNavigation;
        if (!operation || operation.controller.signal !== signal || signal.aborted || destination.#disposed) throw createAbortError('Pane navigation no longer owns transfer admission');
        if (destination === this) {
            const retained = this.#retainedNavigation;
            this.#retainedNavigation = null;
            retained?.controller.abort('navigation-superseded');
            return;
        }
        const predecessor = destination.#activeNavigation;
        const retained = destination.#retainedNavigation;
        destination.#retainedNavigation = null;
        this.#activeNavigation = this.#retainedNavigation;
        this.#retainedNavigation = null;
        if (this.#latestNavigationCompletion === operation.completion) this.#latestNavigationCompletion = this.#activeNavigation?.completion ?? null;
        operation.owner = destination.#navigationOwner;
        destination.#activeNavigation = operation;
        destination.#latestNavigationCompletion = operation.completion;
        retained?.controller.abort('navigation-superseded');
        predecessor?.controller.abort('navigation-superseded');
        this.localization.resume();
    }

    #settleNavigation(operation: RoutePaneNavigation): void {
        if (this.#retainedNavigation === operation) this.#retainedNavigation = null;
        if (this.#activeNavigation === operation) {
            this.#activeNavigation = this.#retainedNavigation;
            this.#retainedNavigation = null;
            if (this.#activeNavigation) this.#latestNavigationCompletion = this.#activeNavigation.completion;
            else {
                this.outlet.cancelActive('navigation-settled');
                this.localization.resume();
            }
        }
        this.#onNavigationSettled();
    }

    setNavigationCommitted(signal: AbortSignal, committed: boolean): boolean {
        const navigation = [this.#activeNavigation, this.#retainedNavigation].find((candidate) => candidate?.controller.signal === signal);
        if (!navigation) return false;
        navigation.committed = committed;
        return true;
    }

    getLatestNavigationCompletion(): Promise<void> | null {
        return this.#latestNavigationCompletion;
    }

    getRequestedRoute(): string | null {
        return this.#activeNavigation?.request.path ?? null;
    }

    get isDisposed(): boolean {
        return this.#disposed;
    }

    cancel(reason: string): void {
        const navigation = this.#activeNavigation;
        const retained = this.#retainedNavigation;
        this.#activeNavigation = null;
        this.#retainedNavigation = null;
        retained?.controller.abort(reason);
        navigation?.controller.abort(reason);
        this.outlet.cancelActive(reason);
    }

    captureCancellation(reason: string): () => void {
        const captured = this.#activeNavigation;
        return () => {
            const owner = captured?.owner ?? this.#navigationOwner;
            owner.cancel(captured, reason);
        };
    }

    captureSessionCancellation(reason: string): { seal(): void; cancel(): void } {
        const host = this.outlet.peekPageHost()?.captureCancellation(reason);
        const cancelNavigation = this.captureCancellation(reason);
        const retained = this.#retainedNavigation;
        return {
            seal: () => host?.seal(),
            cancel: () => {
                const failures: Error[] = [];
                runCleanupStepCollectingFailure(() => host?.cancel(), failures);
                runCleanupStepCollectingFailure(() => retained?.controller.abort(reason), failures);
                runCleanupStepCollectingFailure(cancelNavigation, failures);
                throwCollectedCleanupFailures(failures);
            }
        };
    }

    setPresentation({ visible, focused }: { visible: boolean; focused: boolean }): void {
        RoutePane.setPresentations([{ pane: this, visible, focused }]);
    }

    static setPresentations(changes: readonly { pane: RoutePane; visible: boolean; focused: boolean }[], beforeNotify?: () => void): void {
        const identities = new Set<RoutePane>();
        for (const change of changes) {
            if (identities.has(change.pane)) throw new Error('A pane presentation batch requires unique owners');
            identities.add(change.pane);
        }
        const notifications: { pane: RoutePane; token: symbol }[] = [];
        for (const { pane, visible, focused } of changes) {
            if (pane.#visible === visible && pane.#focused === focused) continue;
            const token = Symbol('pane-presentation');
            pane.#presentationToken = token;
            pane.#visible = visible;
            pane.#focused = focused;
            notifications.push({ pane, token });
        }
        const failures: Error[] = [];
        if (beforeNotify) runCleanupStepCollectingFailure(beforeNotify, failures);
        for (const { pane, token } of notifications) {
            for (const listener of [...pane.#presentationListeners]) {
                if (pane.#presentationToken !== token) break;
                if (!pane.#presentationListeners.has(listener)) continue;
                try {
                    listener();
                } catch (error) {
                    failures.push(ensureError(error));
                }
            }
        }
        if (failures.length) throw new AggregateError(failures, 'Pane presentation notification failed');
    }

    disposeNavigation(): void {
        this.#disposed = true;
        this.localization.dispose();
        this.#latestNavigationCompletion = null;
        this.#presentationListeners.clear();
        this.cancel('router-destroyed');
    }
}

export { RoutePane };
export type { RoutePaneDependencies };
