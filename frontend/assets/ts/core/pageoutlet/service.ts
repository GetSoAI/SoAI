/* SoAI - Shared page outlet service [frontend/assets/ts/core/pageoutlet/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { isPageRegistry } from '@core/pagehost/guards.ts';
import type { PageInstance, PageRegistry } from '@core/pagehost/types.ts';
import { PageHost } from '@core/pagehost/service.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { isFunction, isString } from '@core/typeGuards.ts';
import { awaitCommitWindow, awaitStageWithTimeout, runPreNavigationCleanup } from '@core/pageoutlet/actions.ts';
import { PAGE_OUTLET_RENDER_STAGES, READY_TIMEOUT_MS } from '@core/pageoutlet/constants.ts';
import { resolveContainer } from '@core/pageoutlet/dom.ts';
import { completePageOutletRender } from '@core/pageoutlet/renderCompletion.ts';
import { reportPageOutletRenderFailure } from '@core/pageoutlet/renderFailure.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { type PageHostInstance, type PageOutletConstructorOptions, type PageOutletDestroyOptions, type PageOutletEventEmitter, type PageOutletRenderOptions } from '@core/pageoutlet/types.ts';
import { PageOutletOverlayController } from '@core/pageoutlet/overlayController.ts';
import { PageOutletVisualTransaction } from '@core/pageoutlet/visualTransaction.ts';
import { isAbortError, raceWithAbortSignal } from '@core/errors/abort.ts';
import { createDeferred } from '@core/runtime/deferred.ts';

class PageOutlet {
    #resources = new ResourceTracker();
    #container: HTMLElement | null;
    #pageHost: PageHostInstance | null;
    #activeToken: symbol | null;
    #emitEvent: PageOutletEventEmitter | null;
    #pageRegistry: PageRegistry | null;
    #onPreservedPageFailure: (() => void) | null;
    #overlayController: PageOutletOverlayController;
    #visualTransaction: PageOutletVisualTransaction;
    #readyTimeout: number;
    #commitToken: symbol | null = null;
    #commitCompletion: Promise<void> | null = null;
    #supersededPage: PageInstance | null = null;
    #settleSupersededNavigation: (() => void) | null = null;
    constructor({ emitEvent = null, onPreservedPageFailure = null, onRetry = null, pageRegistry = null }: PageOutletConstructorOptions = {}) {
        this.#container = null;
        this.#pageHost = null;
        this.#activeToken = null;
        this.#emitEvent = isFunction(emitEvent) ? emitEvent : null;
        this.#onPreservedPageFailure = isFunction(onPreservedPageFailure) ? onPreservedPageFailure : null;
        if (pageRegistry !== null && !isPageRegistry(pageRegistry)) {
            throw new Error('PageOutlet requires a valid page registry');
        }
        this.#pageRegistry = pageRegistry;
        this.#overlayController = new PageOutletOverlayController({
            resources: this.#resources,
            clearSkeleton: () => this.clearSkeleton()
        });
        this.#visualTransaction = new PageOutletVisualTransaction({
            resources: this.#resources,
            setReady: () => this.#overlayController.setState('ready'),
            showLoading: (label, detail, delayed) => {
                this.#overlayController.setState('loading', { label, detail, delayed });
            }
        });
        this.#overlayController.setRetryHandler(isFunction(onRetry) ? onRetry : null);
        this.#readyTimeout = READY_TIMEOUT_MS;
    }
    #isActiveRender = (token: symbol): boolean => this.#activeToken === token;
    setContainer(target: HTMLElement | string): this {
        const resolved = resolveContainer(target);
        if (this.#container === resolved) {
            return this;
        }
        const previousContainer = this.#container;
        if (previousContainer !== resolved && this.#pageHost?.getCurrent()) {
            throw new Error('PageOutlet cannot change containers while a page is mounted');
        }
        this.#container = resolved;
        this.#container.dataset['pageOutletRoot'] = 'true';
        this.#overlayController.setContainer(this.#container);
        this.#visualTransaction.setContainer(this.#container);
        if (previousContainer !== resolved && this.#pageHost) {
            this.#pageHost.cancelPrepared('container-changed');
            this.#pageHost = null;
        }
        return this;
    }
    getContainer(): HTMLElement {
        return this.#requireContainer();
    }
    getPageHost(): PageHostInstance {
        if (!this.#container) {
            throw new Error('PageOutlet requires a container before resolving PageHost');
        }
        if (!this.#pageHost) {
            if (!this.#pageRegistry) {
                throw new Error('PageOutlet requires a page registry before resolving PageHost');
            }
            this.#pageHost = new PageHost({ container: this.#container, registry: this.#pageRegistry });
        }
        return this.#pageHost;
    }
    setSkeleton(route: string): void {
        if (!isString(route) || !route.trim()) {
            throw new Error('PageOutlet skeleton requires a route identifier');
        }
        const container = this.#requireContainer();
        container.dataset['routeSkeleton'] = route.trim();
        this.#overlayController.setState('loading', {
            label: i18n.t('pageOutlet.loading')
        });
    }
    private clearSkeleton(): void {
        delete this.#requireContainer().dataset['routeSkeleton'];
    }
    getState(): string {
        return this.#overlayController.getState();
    }
    waitForCommit(): Promise<void> {
        return this.#commitCompletion ?? Promise.resolve();
    }
    async render({ component, parameters = {}, refresh = false, beforePrepare = null, beforeCommit = null, commitNavigation, readyTimeoutMs = this.#readyTimeout, signal }: PageOutletRenderOptions = {}): Promise<{ name: string; instance: PageInstance } | null> {
        if (!isString(component) || !component.trim()) {
            throw new Error('PageOutlet render requires a non-empty component name');
        }
        if (signal?.aborted) return null;
        const pendingCommit = this.#commitCompletion;
        if (pendingCommit) {
            const commitAvailable = await awaitCommitWindow(pendingCommit, signal);
            if (!commitAvailable) return null;
        }
        if (signal?.aborted) return null;
        runPreNavigationCleanup();
        const host = this.getPageHost();
        this.#activeToken = null;
        host.cancelPrepared('superseded');
        const token = Symbol(component);
        this.#activeToken = token;
        const visualToken = this.#visualTransaction.begin();
        const trimmedComponent = component.trim();
        const startedAt = performance.now();
        let pageCommitted = false;
        let preparedPage: PageInstance | null = null;
        const cancelRender = (): void => {
            if (!this.#isActiveRender(token)) return;
            if (this.#commitToken === token) return;
            this.#activeToken = null;
            this.#visualTransaction.supersede(visualToken);
            host.cancelPrepared('navigation-superseded');
        };
        signal?.addEventListener('abort', cancelRender, { once: true });
        this.#emitEventInternal('component:load:start', { component: trimmedComponent, refresh });
        errorHandler.info('PageOutlet', 'Component load start', { component: trimmedComponent, refresh });
        try {
            await this.#runRenderHook(beforePrepare, signal);
            if (!this.#isActiveRender(token)) return null;
            await this.#visualTransaction.preparePageExit(visualToken);
            if (!this.#isActiveRender(token)) return null;
            this.#visualTransaction.showPreparationLoading(visualToken);
            const preparation = awaitStageWithTimeout(
                async () => {
                    preparedPage = await host.prepare(trimmedComponent, parameters);
                },
                readyTimeoutMs,
                token,
                trimmedComponent,
                PAGE_OUTLET_RENDER_STAGES.PREPARED,
                (activeToken: symbol): boolean => this.#activeToken === activeToken,
                () => host.cancelPrepared(`page-timeout:${trimmedComponent}`)
            );
            await (signal ? raceWithAbortSignal(preparation, signal) : preparation);
            if (!this.#isActiveRender(token)) return null;
            const commit = createDeferred<void>();
            this.#commitToken = token;
            this.#commitCompletion = commit.promise;
            try {
                await this.#runRenderHook(beforeCommit, undefined);
                if (this.#supersededPage && host.getCurrent()?.instance === this.#supersededPage) {
                    host.cancelCurrent(this.#supersededPage, 'navigation-superseded');
                }
                this.#supersededPage = null;
                this.#settleSupersededNavigation = null;
                const committedPage = await host.commitPrepared();
                if (!committedPage || committedPage !== preparedPage) throw new Error(`Prepared page ${trimmedComponent} lost commit ownership`);
                pageCommitted = true;
                if (signal?.aborted || !this.#isActiveRender(token)) {
                    this.#supersededPage = committedPage;
                    this.#settleSupersededNavigation = commitNavigation ?? null;
                    this.#visualTransaction.supersede(visualToken);
                } else {
                    commitNavigation?.();
                    if (signal?.aborted || !this.#isActiveRender(token)) {
                        this.#supersededPage = committedPage;
                        this.#visualTransaction.supersede(visualToken);
                    }
                }
            } finally {
                this.#commitToken = null;
                this.#commitCompletion = null;
                commit.resolve(undefined);
            }
            if (signal?.aborted || !this.#isActiveRender(token)) return null;
            const readiness = awaitStageWithTimeout(
                async () => host.whenReady({ waitForReveal: false }),
                readyTimeoutMs,
                token,
                trimmedComponent,
                PAGE_OUTLET_RENDER_STAGES.PREPARED,
                (activeToken: symbol): boolean => this.#activeToken === activeToken,
                () => host.destroyCurrent({ force: true, reason: `page-timeout:${trimmedComponent}` })
            );
            await (signal ? raceWithAbortSignal(readiness, signal) : readiness);
            if (!this.#isActiveRender(token)) return null;
            try {
                await this.#visualTransaction.revealEnteredPage(visualToken);
            } catch (error) {
                errorHandler.warn('PageOutlet', `Page ${trimmedComponent} enter animation failed`, ensureError(error));
                this.#visualTransaction.completeRevealAfterFailure(visualToken);
            }
            if (!this.#isActiveRender(token)) return null;
            this.#visualTransaction.commit(visualToken);
            host.allowReveal();
            if (this.#activeToken !== token) {
                return null;
            }
            completePageOutletRender(
                {
                    component: trimmedComponent,
                    refresh,
                    startedAt
                },
                {
                    emitEvent: this.#emitEventInternal
                }
            );
            return host.getCurrent();
        } catch (error) {
            if (!pageCommitted && preparedPage !== null && host.getCurrent()?.instance === preparedPage) {
                pageCommitted = true;
            }
            const ownsCommittedPage = pageCommitted && preparedPage !== null && host.getCurrent()?.instance === preparedPage;
            if ((isAbortError(error) || signal?.aborted) && ownsCommittedPage) {
                this.#supersededPage = preparedPage;
                this.#visualTransaction.supersede(visualToken);
                return null;
            }
            if (!this.#isActiveRender(token)) return null;
            const settledSupersededPage = !pageCommitted && this.#settleSupersededPage(host);
            this.#visualTransaction.fail(visualToken);
            if (settledSupersededPage) host.allowReveal();
            host.cancelPrepared('render-failed');
            if (isAbortError(error) || signal?.aborted || !this.#isActiveRender(token)) return null;
            if (pageCommitted && preparedPage !== null && host.getCurrent()?.instance === preparedPage) {
                try {
                    await host.destroyCurrent({ force: true, reason: 'render-failed' });
                } catch (teardownError) {
                    errorHandler.warn('PageOutlet', `Failed to teardown page ${trimmedComponent} after render failure`, ensureError(teardownError));
                }
            }
            const runtimeError = ensureError(error);
            reportPageOutletRenderFailure(
                { component: trimmedComponent, refresh, startedAt, error: runtimeError },
                {
                    applyErrorState: (runtimeError: Error): void => {
                        if (host.getCurrent() && !pageCommitted) {
                            this.#overlayController.setState('ready');
                            this.#onPreservedPageFailure?.();
                            return;
                        }
                        this.#overlayController.applyErrorState(runtimeError);
                    },
                    emitEvent: this.#emitEventInternal
                }
            );
            throw runtimeError;
        } finally {
            signal?.removeEventListener('abort', cancelRender);
            if (this.#activeToken === token) {
                this.#activeToken = null;
            }
        }
    }
    async destroyCurrent({ force = true }: PageOutletDestroyOptions = {}): Promise<void> {
        if (this.#commitCompletion) await this.#commitCompletion;
        const host = this.#pageHost;
        this.#activeToken = null;
        if (this.#container) this.#visualTransaction.cancel();
        if (host) {
            await host.destroyCurrent({ force });
        }
        if (this.#container) this.#overlayController.setState('idle');
    }
    cancelActive(reason: string = 'cancelled'): void {
        if (this.#commitToken !== null) return;
        this.#activeToken = null;
        const host = this.#pageHost;
        const settledSupersededPage = host ? this.#settleSupersededPage(host) : false;
        this.#supersededPage = null;
        this.#settleSupersededNavigation = null;
        if (this.#container) this.#visualTransaction.cancel();
        if (settledSupersededPage) host?.allowReveal();
        host?.cancelPrepared(reason);
    }
    async destroy(): Promise<void> {
        await this.destroyCurrent({ force: true });
        this.#resources.cleanup();
        this.#pageHost = null;
        this.#activeToken = null;
        this.#supersededPage = null;
        this.#settleSupersededNavigation = null;
    }
    #settleSupersededPage(host: PageHostInstance): boolean {
        const page = this.#supersededPage;
        if (!page || host.getCurrent()?.instance !== page) return false;
        const settleNavigation = this.#settleSupersededNavigation;
        this.#supersededPage = null;
        this.#settleSupersededNavigation = null;
        settleNavigation?.();
        return true;
    }
    async #runRenderHook(hook: (() => void | Promise<void>) | Promise<void> | null, signal: AbortSignal | undefined): Promise<void> {
        if (!hook) return;
        const task = typeof hook === 'function' ? Promise.resolve(hook()) : Promise.resolve(hook);
        await (signal ? raceWithAbortSignal(task, signal) : task);
    }
    #emitEventInternal = (stage: string, payload: Record<string, JsonValue> = {}, severity: string = 'info'): void => {
        if (this.#emitEvent) {
            this.#emitEvent(stage, payload, severity);
        }
    };
    #requireContainer = (): HTMLElement => {
        if (!this.#container) {
            throw new Error('PageOutlet requires a container before performing this action');
        }
        return this.#container;
    };
}
export { PageOutlet };
