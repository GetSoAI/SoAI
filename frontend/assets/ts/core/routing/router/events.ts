/* SoAI - Shared routing router events [frontend/assets/ts/core/routing/router/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readErrorMessage } from '@core/routing/router/navigationMiddlewareNormalization.ts';
import type { ErrorHandlerService, ResourceTrackerInstance } from '@core/routing/router/routerDependencies.ts';
import type { NavigationOptions, RouteEntry, RouteParameters } from '@core/routing/router/types.ts';
import { isRecordLike } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { claimErrorReporting } from '@core/errors/reportingOwnership.ts';
import { notifyHandledOperationError } from '@core/operationErrorNotifier.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { capturePagePaneHistoryEntry, createPagePaneHistoryState } from '@core/pagepanes/history.ts';
import { subscribeNavigationProtection } from '@core/navigationGuards.ts';

interface BrowserNavigationTarget {
    readonly paneId: string | null;
    readonly focusIntent: number;
}

interface RouterBrowserNavigationDependencies {
    getWindow(): Window;
    getRouteFromHash(): string | null;
    parseHash(hash: string): string | null;
    parseRoute: (target: string) => { route: RouteEntry; parameters: RouteParameters } | null;
    getDefaultRoute(): string;
    isBrowserNavigationSuspended(): boolean;
    claimFocusIntent(): number;
    isCurrentFocusIntent(intent: number): boolean;
    getFocusedPaneId(): string | null;
    navigate(target: string, options: NavigationOptions, intent: BrowserNavigationTarget): Promise<void>;
    errorHandler: ErrorHandlerService;
}

interface RouterBrowserIntent {
    readonly sequence: number;
    readonly focusIntent: number;
    url: string;
    type: 'navigation' | 'selection' | 'traversal';
    paneId: string | null;
}

class RouterBrowserNavigation {
    readonly #dependencies: RouterBrowserNavigationDependencies;
    readonly #sequence = new SequenceToken();
    #current: RouterBrowserIntent | null = null;
    #observedUrl: string;
    #expectedPair: { oldUrl: string; newUrl: string } | null = null;
    #reportedIncompatible = false;

    constructor(dependencies: RouterBrowserNavigationDependencies) {
        this.#dependencies = dependencies;
        this.#observedUrl = dependencies.getWindow().location.href;
    }

    get focusIntent(): number | null {
        return this.#current?.focusIntent ?? null;
    }

    claim(focusIntent: number): void {
        if (!this.#dependencies.isCurrentFocusIntent(focusIntent)) return;
        const win = this.#dependencies.getWindow();
        this.#current = { sequence: this.#sequence.next(), focusIntent, url: win.location.href, type: 'selection', paneId: this.#dependencies.getFocusedPaneId() };
        this.#observedUrl = win.location.href;
    }

    markNavigation(focusIntent: number): void {
        const intent = this.#current;
        if (intent?.focusIntent === focusIntent && this.#ownsEntry(intent)) intent.type = 'navigation';
    }

    select(paneId: string, route: string, title: string): boolean {
        const intent = this.#current;
        if (!intent || !this.#ownsEntry(intent) || this.#dependencies.getFocusedPaneId() !== paneId) return false;
        intent.type = 'selection';
        intent.paneId = paneId;
        return this.project(route, paneId, 'replace', intent.focusIntent, { title });
    }

    #ownsEntry(intent: RouterBrowserIntent): boolean {
        return this.#current === intent && this.#sequence.isActive(intent.sequence) && this.#dependencies.isCurrentFocusIntent(intent.focusIntent) && this.#dependencies.getWindow().location.href === intent.url;
    }

    receive = (event: Event): void => {
        const dependencies = this.#dependencies;
        if (dependencies.isBrowserNavigationSuspended()) return;
        const win = dependencies.getWindow();
        const url = win.location.href;
        const previousUrl = this.#observedUrl;
        const isTraversal = typeof PopStateEvent === 'function' && event instanceof PopStateEvent;
        const entry = capturePagePaneHistoryEntry(isTraversal ? event.state : win.history.state);
        if (typeof HashChangeEvent === 'function' && event instanceof HashChangeEvent) {
            const pair = this.#expectedPair;
            if (pair && event.oldURL === pair.oldUrl && event.newURL === pair.newUrl) {
                this.#expectedPair = null;
                return;
            }
            if (event.newURL !== url) return;
            this.#expectedPair = null;
        }
        const focusIntent = dependencies.claimFocusIntent();
        const intent = this.#current;
        if (!intent || intent.focusIntent !== focusIntent || !this.#ownsEntry(intent)) return;
        intent.url = url;
        intent.type = 'traversal';
        this.#observedUrl = url;
        if (isTraversal && new URL(previousUrl).hash !== new URL(url).hash) this.#expectedPair = { oldUrl: previousUrl, newUrl: url };
        try {
            const route = dependencies.parseHash(new URL(url).hash);
            if (!route || !this.#ownsEntry(intent)) return;
            const target = normalizeRouteOrDefault(dependencies, route);
            if (!this.#ownsEntry(intent)) return;
            const hint = entry.hint(route);
            if (hint.type === 'incompatible') this.#reportIncompatible();
            if (!this.#ownsEntry(intent)) return;
            const options: NavigationOptions = target === route ? { pushState: false } : { replace: true, force: true };
            const navigation = dependencies.navigate(target, options, { paneId: target === route ? hint.paneId : null, focusIntent });
            void navigation.catch((error) => reportNavigationEventFailure(dependencies, 'Browser navigation failed', ensureError(error)));
        } catch (error) {
            reportNavigationEventFailure(dependencies, 'Browser navigation failed', ensureError(error));
        }
    };

    project(route: string, paneId: string, mode: 'push' | 'replace' | 'preserve', focusIntent: number | null, { previousRoute, title = '' }: { previousRoute?: string; title?: string } = {}): boolean {
        const intent = this.#current;
        if (!intent || focusIntent === null) return false;
        const followsSelection = intent.type === 'selection' && intent.paneId === paneId && this.#dependencies.getFocusedPaneId() === paneId;
        if ((!followsSelection && intent.focusIntent !== focusIntent) || !this.#ownsEntry(intent)) return false;
        const projectionMode = intent.focusIntent === focusIntent ? mode : 'replace';
        const dependencies = this.#dependencies;
        const currentRoute = dependencies.getRouteFromHash();
        if (previousRoute !== undefined && previousRoute !== currentRoute) return false;
        if (projectionMode === 'preserve' && route !== currentRoute) return false;
        const historyApi = dependencies.getWindow().history;
        try {
            const entry = capturePagePaneHistoryEntry(historyApi.state);
            const hint = entry.hint(currentRoute);
            if (previousRoute !== undefined && hint.type === 'matched' && hint.paneId !== paneId) return false;
            const projection = projectionMode === 'push' ? { state: createPagePaneHistoryState(route, paneId), compatibility: 'supported', changed: true } : entry.project(route, paneId);
            if (projection.compatibility === 'incompatible') this.#reportIncompatible();
            if (!this.#ownsEntry(intent)) return false;
            if (projectionMode !== 'push' && route === currentRoute && !projection.changed) return true;
            if (projectionMode === 'push') historyApi.pushState(projection.state, title, `#${route}`);
            else historyApi.replaceState(projection.state, title, `#${route}`);
            if (this.#current === intent) {
                intent.url = dependencies.getWindow().location.href;
                this.#observedUrl = intent.url;
            }
            return true;
        } catch (error) {
            const failure = new RouterHistoryProjectionError(ensureError(error));
            if (claimErrorReporting(failure)) {
                notifyHandledOperationError(failure);
                dependencies.errorHandler.warn('Router', 'Browser route projection unavailable', failure);
            }
            return false;
        }
    }

    #reportIncompatible(): void {
        if (this.#reportedIncompatible) return;
        this.#reportedIncompatible = true;
        const failure = new RouterHistoryProjectionError(new Error('Pane history metadata is unsupported'));
        notifyHandledOperationError(failure);
        this.#dependencies.errorHandler.warn('Router', 'Pane history hints are unavailable for unsupported metadata', failure);
    }
}

class RouterHistoryProjectionError extends Error {
    readonly code = 'page_pane_history_unavailable';

    constructor(cause: Error) {
        super('Browser navigation projection is unavailable', { cause });
    }
}

interface RouterInitializationEventsDependencies {
    resources: ResourceTrackerInstance;
    getWindow: () => Window;
    browserNavigation: RouterBrowserNavigation;
    errorHandler: ErrorHandlerService;
    renderCriticalError: (message: string) => void;
    refreshLanguage: () => void;
    resumeLanguageRefresh: () => void;
}

const normalizeRouteOrDefault = (dependencies: Pick<RouterBrowserNavigationDependencies, 'parseRoute' | 'getDefaultRoute' | 'errorHandler'>, route: string): string => {
    try {
        const parsed = dependencies.parseRoute(route);
        if (parsed) {
            return route;
        }
    } catch (error) {
        dependencies.errorHandler.warn('Router', 'Unknown route on hashchange; redirecting to default route', ensureError(error));
        return dependencies.getDefaultRoute();
    }
    dependencies.errorHandler.warn('Router', 'Unresolved route on hashchange; redirecting to default route');
    return dependencies.getDefaultRoute();
};

const reportNavigationEventFailure = (dependencies: Pick<RouterInitializationEventsDependencies, 'errorHandler'>, message: string, error: Error): void => {
    if (!claimErrorReporting(error)) {
        return;
    }
    notifyHandledOperationError(error);
    dependencies.errorHandler.error('Router', message, error);
};

const registerRouterInitializationEvents = (dependencies: RouterInitializationEventsDependencies): void => {
    const win = dependencies.getWindow();

    dependencies.resources.addEventListener(win, 'popstate', dependencies.browserNavigation.receive);
    dependencies.resources.addEventListener(win, 'hashchange', dependencies.browserNavigation.receive);

    dependencies.resources.addEventListener(win, 'unhandledrejection', (event: Event) => {
        try {
            const promiseRejectionCtor: typeof PromiseRejectionEvent | null = typeof PromiseRejectionEvent === 'function' ? PromiseRejectionEvent : null;
            const reason = promiseRejectionCtor && event instanceof promiseRejectionCtor ? event.reason : isRecordLike(event) && 'reason' in event ? event.reason : null;
            const message = readErrorMessage(reason);
            if (message && message.includes('navigation')) {
                event.preventDefault();
                dependencies.renderCriticalError('Navigation system error. Please refresh the page.');
            }
        } catch (handlerError) {
            const runtimeError = ensureError(handlerError);
            dependencies.errorHandler.error('Router', 'Unhandled rejection handler failed', runtimeError);
        }
    });

    dependencies.resources.addEventListener(win, 'soai:language:changed', dependencies.refreshLanguage);
    dependencies.resources.addEventListener(win, 'core.modal.close', dependencies.resumeLanguageRefresh);
    dependencies.resources.track(subscribeNavigationProtection(dependencies.resumeLanguageRefresh));
};

export { registerRouterInitializationEvents, reportNavigationEventFailure };
export { RouterBrowserNavigation };
export type { BrowserNavigationTarget, RouterBrowserNavigationDependencies };
