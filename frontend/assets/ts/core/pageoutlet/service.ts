/* SoAI - Shared page outlet service [frontend/assets/ts/core/pageoutlet/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { isPageRegistry } from '@core/pagehost/guards.ts';
import type { PageInstance, PageRegistry } from '@core/pagehost/types.ts';
import { PageHost } from '@core/pagehost/service.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { isFunction, isString } from '@core/typeGuards.ts';
import { awaitStageWithTimeout, runPageOutletRenderHook } from '@core/pageoutlet/actions.ts';
import { PAGE_OUTLET_RENDER_STAGES, READY_TIMEOUT_MS } from '@core/pageoutlet/constants.ts';
import { requirePageOutletContainer, resolveContainer } from '@core/pageoutlet/dom.ts';
import { completePageOutletRender } from '@core/pageoutlet/renderCompletion.ts';
import { PageOutletCleanupError, reportPageOutletRenderFailure } from '@core/pageoutlet/renderFailure.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { type PageHostInstance, type PageOutletConstructorOptions, type PageOutletDestroyOptions, type PageOutletEventEmitter, type PageOutletRenderOptions } from '@core/pageoutlet/types.ts';
import { PageOutletOverlayController } from '@core/pageoutlet/overlayController.ts';
import { PageOutletVisualTransaction } from '@core/pageoutlet/visualTransaction.ts';
import { isAbortError, raceWithAbortSignal } from '@core/errors/abort.ts';
import { PageOutletRenderOwnership } from '@core/pageoutlet/renderOwnership.ts';
import { removeNonPageOutletSlotNodes } from '@core/pageoutlet/slots.ts';

class PageOutlet {
    #resources = new ResourceTracker();
    #container: HTMLElement | null;
    #pageHost: PageHostInstance | null;
    #renderOwnership = new PageOutletRenderOwnership();
    #emitEvent: PageOutletEventEmitter | null;
    #pageRegistry: PageRegistry | null;
    #onPreservedPageFailure: ((error: Error) => void) | null;
    #overlayController: PageOutletOverlayController;
    #visualTransaction: PageOutletVisualTransaction;
    constructor({ emitEvent = null, onPreservedPageFailure = null, onRetry = null, pageRegistry = null, spinnerWorkerUrl, onStateChanged }: PageOutletConstructorOptions = {}) {
        this.#container = null;
        this.#pageHost = null;
        this.#emitEvent = isFunction(emitEvent) ? emitEvent : null;
        this.#onPreservedPageFailure = isFunction(onPreservedPageFailure) ? onPreservedPageFailure : null;
        if (pageRegistry !== null && !isPageRegistry(pageRegistry)) {
            throw new Error('PageOutlet requires a valid page registry');
        }
        this.#pageRegistry = pageRegistry;
        this.#overlayController = new PageOutletOverlayController({
            resources: this.#resources,
            spinnerWorkerUrl,
            onStateChanged
        });
        this.#visualTransaction = new PageOutletVisualTransaction({
            resources: this.#resources,
            setReady: () => this.#overlayController.setState('ready'),
            restoreState: () => this.#overlayController.restoreSettledState(),
            showLoading: (label, detail, delayed) => {
                this.#overlayController.setState('loading', { label, detail, delayed });
            }
        });
        this.#overlayController.setRetryHandler(isFunction(onRetry) ? onRetry : null);
    }
    #isActiveRender = (token: symbol): boolean => this.#renderOwnership.isActive(token);
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
            this.#renderOwnership.cancelActive('container-changed');
            this.#pageHost.cancelPrepared('container-changed');
            this.#pageHost = null;
        }
        return this;
    }
    getContainer(): HTMLElement {
        return requirePageOutletContainer(this.#container);
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
    peekPageHost(): PageHostInstance | null {
        return this.#pageHost;
    }
    setSkeleton(route: string): void {
        this.#overlayController.setSkeleton(route);
    }
    getState(): string {
        return this.#overlayController.getState();
    }
    async waitForCommit(): Promise<void> {
        await this.#renderOwnership.waitForCommit();
    }
    async render({ component, parameters = {}, refresh = false, beforePrepare = null, beforeCommit = null, finalAdmission, commitNavigation, mountPublication, afterCommit, readyTimeoutMs = READY_TIMEOUT_MS, signal, createMountScope }: PageOutletRenderOptions): Promise<{ name: string; instance: PageInstance } | null> {
        if (!isString(component) || !component.trim()) {
            throw new Error('PageOutlet render requires a non-empty component name');
        }
        if (signal?.aborted) return null;
        if (!(await this.#renderOwnership.waitForCommit(readyTimeoutMs, signal))) return null;
        if (signal?.aborted) return null;
        const host = this.getPageHost();
        const token = Symbol(component);
        const renderScope = this.#renderOwnership.begin(token, signal, mountPublication);
        const renderSignal = renderScope.signal;
        if (renderSignal.aborted || !this.#isActiveRender(token)) {
            renderScope.finish();
            return null;
        }
        host.cancelPrepared('superseded');
        const visualToken = this.#visualTransaction.begin();
        const trimmedComponent = component.trim();
        const startedAt = performance.now();
        let preparedPage: PageInstance | null = null;
        const cancelRender = (): void => {
            if (!this.#isActiveRender(token)) return;
            if (this.#renderOwnership.isCommitting(token)) return;
            this.#renderOwnership.cancel(token, 'navigation-superseded');
            this.#visualTransaction.supersede(visualToken);
            host.cancelPrepared('navigation-superseded');
        };
        renderSignal.addEventListener('abort', cancelRender, { once: true });
        this.#emitEvent?.('component:load:start', { component: trimmedComponent, refresh }, 'info');
        errorHandler.info('PageOutlet', 'Component load start', { component: trimmedComponent, refresh });
        try {
            await awaitStageWithTimeout(
                () => runPageOutletRenderHook(beforePrepare, renderSignal),
                readyTimeoutMs,
                token,
                trimmedComponent,
                PAGE_OUTLET_RENDER_STAGES.PREPARED,
                this.#isActiveRender,
                () => host.cancelPrepared('before-prepare-timeout'),
                renderSignal
            );
            if (!this.#isActiveRender(token)) return null;
            await this.#visualTransaction.preparePageExit(visualToken);
            if (!this.#isActiveRender(token)) return null;
            this.#visualTransaction.showPreparationLoading(visualToken);
            const preparation = awaitStageWithTimeout(
                async () => {
                    preparedPage = await host.prepare(trimmedComponent, parameters, { signal: renderSignal, createMountScope });
                },
                readyTimeoutMs,
                token,
                trimmedComponent,
                PAGE_OUTLET_RENDER_STAGES.PREPARED,
                (activeToken: symbol): boolean => this.#isActiveRender(activeToken),
                () => host.cancelPrepared(`page-timeout:${trimmedComponent}`),
                renderSignal
            );
            await preparation;
            if (!this.#isActiveRender(token)) return null;
            await this.#renderOwnership.commit(
                token,
                async () => {
                    try {
                        await runPageOutletRenderHook(beforeCommit, renderSignal);
                        const committedPage = await host.commitPrepared({ signal: renderSignal, finalAdmission, mountPublication: renderScope.mountPublication, afterCommit });
                        if (!committedPage || committedPage !== preparedPage) throw new Error(`Prepared page ${trimmedComponent} lost commit ownership`);
                        if (renderScope.expired) return;
                        this.#renderOwnership.clearSuperseded();
                        renderScope.committed = true;
                        if (renderSignal.aborted || !this.#isActiveRender(token)) {
                            this.#renderOwnership.retainSuperseded(committedPage, commitNavigation ?? null);
                            this.#visualTransaction.supersede(visualToken);
                        } else {
                            commitNavigation?.();
                            if (renderSignal.aborted || !this.#isActiveRender(token)) {
                                this.#renderOwnership.retainSuperseded(committedPage);
                                this.#visualTransaction.supersede(visualToken);
                            }
                        }
                    } finally {
                        if (renderScope.expired && preparedPage) await host.destroyCurrent({ expectedInstance: preparedPage, reason: 'resource-release-unconfirmed' });
                    }
                },
                {
                    component: trimmedComponent,
                    timeoutMs: readyTimeoutMs,
                    expire: () => {
                        renderScope.expire();
                        if (preparedPage) host.cancelCurrent(preparedPage, 'resource-release-unconfirmed');
                    }
                }
            );
            if (renderSignal.aborted || !this.#isActiveRender(token)) {
                if (preparedPage && host.getCurrent()?.instance === preparedPage) this.#renderOwnership.retainSuperseded(preparedPage);
                this.#visualTransaction.supersede(visualToken);
                return null;
            }
            const readiness = awaitStageWithTimeout(
                async () => host.whenReady({ waitForReveal: false }),
                readyTimeoutMs,
                token,
                trimmedComponent,
                PAGE_OUTLET_RENDER_STAGES.PREPARED,
                (activeToken: symbol): boolean => this.#isActiveRender(activeToken),
                () => {
                    const page = preparedPage;
                    if (!page) return;
                    return this.#renderOwnership.dispose(
                        () => host.destroyCurrent({ expectedInstance: page, force: true, reason: `page-timeout:${trimmedComponent}` }),
                        () => {},
                        false,
                        readyTimeoutMs,
                        token
                    );
                },
                renderSignal
            );
            await readiness;
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
            if (!this.#isActiveRender(token)) {
                return null;
            }
            completePageOutletRender(
                {
                    component: trimmedComponent,
                    refresh,
                    startedAt
                },
                {
                    emitEvent: this.#emitEvent ?? undefined
                }
            );
            return host.getCurrent();
        } catch (error) {
            if (!renderScope.committed && preparedPage !== null && host.getCurrent()?.instance === preparedPage) {
                renderScope.committed = true;
            }
            const ownsCommittedPage = renderScope.committed && preparedPage !== null && host.getCurrent()?.instance === preparedPage;
            if (!renderScope.expired && (isAbortError(error) || renderSignal.aborted) && ownsCommittedPage && preparedPage !== null) {
                this.#renderOwnership.retainSuperseded(preparedPage);
                this.#visualTransaction.supersede(visualToken);
                return null;
            }
            if (!this.#isActiveRender(token)) return null;
            const settledSupersededPage = !renderScope.committed && this.#renderOwnership.settleSuperseded(host.getCurrent()?.instance ?? null);
            this.#visualTransaction.fail(visualToken);
            if (settledSupersededPage) host.allowReveal();
            host.cancelPrepared('render-failed');
            if (!renderScope.expired && (isAbortError(error) || renderSignal.aborted || !this.#isActiveRender(token))) return null;
            let runtimeError = ensureError(error);
            if (!renderScope.expired && renderScope.committed && preparedPage !== null && host.getCurrent()?.instance === preparedPage) {
                const page = preparedPage;
                try {
                    await raceWithAbortSignal(
                        this.#renderOwnership.dispose(
                            () => host.destroyCurrent({ expectedInstance: page, force: true, reason: 'render-failed' }),
                            () => {},
                            false,
                            readyTimeoutMs,
                            token
                        ),
                        renderSignal
                    );
                } catch (teardownError) {
                    runtimeError = new PageOutletCleanupError(runtimeError, ensureError(teardownError));
                }
            }
            if (!this.#isActiveRender(token) || (!renderScope.expired && renderSignal.aborted)) return null;
            reportPageOutletRenderFailure(
                { component: trimmedComponent, refresh, startedAt, error: runtimeError },
                {
                    overlay: this.#overlayController,
                    preserveCurrentPage: host.getCurrent() !== null && !renderScope.committed,
                    onPreservedPageFailure: this.#onPreservedPageFailure,
                    emitEvent: this.#emitEvent ?? undefined
                }
            );
            throw runtimeError;
        } finally {
            renderSignal.removeEventListener('abort', cancelRender);
            renderScope.finish();
        }
    }
    destroyCurrent({ force = true }: PageOutletDestroyOptions = {}): Promise<void> {
        return this.#dispose(force, false);
    }
    whenReleased(): Promise<void> {
        return this.#renderOwnership.whenReleased();
    }
    #dispose(force: boolean, final: boolean): Promise<void> {
        return this.#renderOwnership.dispose(
            async () => {
                const host = this.#pageHost;
                const container = this.#container;
                if (container) this.#visualTransaction.cancel();
                if (host) await host.destroyCurrent({ force });
                if (container && this.#container === container && this.#pageHost === host) {
                    removeNonPageOutletSlotNodes(container);
                    this.#overlayController.setState('idle');
                }
            },
            async () => {
                await this.#resources.cleanup({ requireComplete: true });
                this.#pageHost = null;
                this.#renderOwnership.clearSuperseded();
            },
            final,
            READY_TIMEOUT_MS
        );
    }

    cancelActive(reason: string = 'cancelled'): void {
        this.#renderOwnership.cancelRender(reason, this.#pageHost, this.#container ? this.#visualTransaction : null);
    }
    destroy(): Promise<void> {
        return this.#dispose(true, true);
    }
}
export { PageOutlet };
