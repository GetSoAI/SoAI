/* SoAI - Routed page runtime readiness, cancellation, and listener-scope ownership [frontend/assets/ts/core/routing/pages/basepage/PageLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getLocation, getRequestAnimationFrame } from '@core/environment/public.ts';
import { ErrorBoundary } from '@core/ErrorBoundary.ts';
import { LifecycleScope } from '@core/lifecycle/lifecycleScope.ts';
import { err } from '@core/routing/pages/basepagecore/actions.ts';
import { initializeBasePageLifecycle, refreshBasePageLifecycle, runBasePageStandardSetup } from '@core/routing/pages/basepage/service.ts';
import { PageTeardown } from '@core/routing/pages/basepage/PageTeardown.ts';
import { PageRuntime } from '@core/runtime/PageRuntime.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { PageDestroyCommand, PageInitializationCommand, PageLifecycleDependencies, PageRefreshCommand } from '@core/routing/pages/basepage/pageLifecycleContracts.ts';
import { isFunction } from '@core/typeGuards.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { LifecycleCancellationError, isLifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import { isAbortError, throwIfAborted } from '@core/errors/abort.ts';
import { PageActivationGate } from '@core/routing/pages/basepage/PageActivationGate.ts';
import { createDeferred } from '@core/runtime/deferred.ts';

type PageInitializationTask = Promise<boolean | void>;

class PageLifecycle {
    readonly #dependencies: PageLifecycleDependencies;
    readonly #runtime: PageRuntime;
    readonly #boundary: ErrorBoundary;
    readonly #teardown: PageTeardown;
    readonly #initializeScope = new LifecycleScope();
    readonly #listenersScope = new LifecycleScope();
    readonly #detachedScopes: Map<string, LifecycleScope> = new Map();
    readonly #activation = new PageActivationGate();
    #initialized = false;
    #destroyed = false;
    #initializePromise: Promise<boolean> | null = null;
    #initializeTask: Promise<void> | null = null;
    #destroyTask: Promise<boolean> | null = null;
    #hideTask: Promise<void> | null = null;
    #generation = 0;
    #transitionCallbackDepth = 0;

    constructor(dependencies: PageLifecycleDependencies) {
        this.#dependencies = dependencies;
        this.#runtime = new PageRuntime({ pageId: dependencies.pageId });
        this.#boundary = new ErrorBoundary(dependencies.pageId || 'BasePage');
        this.#teardown = new PageTeardown(dependencies);
    }

    get runtime(): PageRuntime {
        return this.#runtime;
    }

    get isInitialized(): boolean {
        return this.#initialized;
    }

    get isDestroyed(): boolean {
        return this.#destroyed;
    }

    whenReady(options?: { waitForData?: boolean; waitForReveal?: boolean }): Promise<void> {
        return this.#runtime.whenReady(options);
    }

    allowReveal(): void {
        this.#runtime.allowReveal();
    }

    signal(): AbortSignal | null {
        return this.#runtime.currentSignal();
    }

    async run<T>(operation: string, task: () => Promise<T> | T): Promise<T> {
        return await this.#boundary.execute(task, operation);
    }

    runDetached(operation: string, task: (signal: AbortSignal) => Promise<void> | void): void {
        const scope = this.#detachedScopes.get(operation) ?? new LifecycleScope();
        this.#detachedScopes.set(operation, scope);
        const run = scope.begin(`${operation}-superseded`);
        if (!scope.isCurrent(run)) return;
        const detachedTask = this.#boundary
            .execute(() => task(run.signal), operation)
            .finally(() => {
                if (scope.isCurrent(run)) {
                    if (this.#detachedScopes.get(operation) === scope) this.#detachedScopes.delete(operation);
                    scope.abort(`${operation}-complete`);
                }
            });
        void detachedTask.catch((error) => {
            if (!isAbortError(error)) {
                errorHandler.debug(this.#dependencies.pageId, `Detached operation rejection settled: ${operation}`, ensureError(error));
            }
        });
    }

    async initialize(parameters: JsonObject | undefined, command: PageInitializationCommand): Promise<void> {
        if (this.#destroyTask) throw new LifecycleCancellationError(`${this.#dependencies.pageId} initialization rejected during destruction`, 'page-destroying');
        if (this.#hideTask) throw new LifecycleCancellationError(`${this.#dependencies.pageId} initialization rejected during hide`, 'page-hiding');
        const previousTask = this.#initializeTask;
        const completion = createDeferred<void>();
        const task = completion.promise;
        this.#initializeTask = task;
        const initializeRun = this.#initializeScope.begin('reinitialize');
        const operation = (async (): Promise<void> => {
            if (previousTask) await this.#settleInitialization(previousTask);
            if (!this.#initializeScope.isCurrent(initializeRun)) return;
            await initializeBasePageLifecycle(
                {
                    pageId: this.#dependencies.pageId,
                    runtime: this.#runtime,
                    phases: this.#activation.phases(command.readiness),
                    pageHost: this.#dependencies.pageHost,
                    pageDom: this.#dependencies.pageDom,
                    layout: this.#dependencies.layout,
                    isDestroyed: this.#destroyed,
                    isInitialized: this.#initialized,
                    resetLifecycleState: () => this.#resetState(),
                    render: command.render,
                    initialize: (initializeParameters, context) => this.#initialize(initializeParameters, command, context),
                    onRefresh: command.refresh
                },
                parameters,
                { signal: initializeRun.signal }
            );
        })();
        void operation.then(completion.resolve, (error) => completion.reject(ensureError(error)));
        try {
            await task;
        } finally {
            if (this.#initializeTask === task) this.#initializeTask = null;
            if (this.#initializeScope.isCurrent(initializeRun)) this.#initializeScope.abort('initialize-complete');
        }
    }

    async #initialize(parameters: JsonObject | null, command: PageInitializationCommand, context: { signal?: AbortSignal }): Promise<boolean> {
        if (this.#destroyTask) throw new LifecycleCancellationError(`${this.#dependencies.pageId} initialization rejected during destruction`, 'page-destroying');
        if (this.#initializePromise) {
            return await this.#initializePromise;
        }
        if (this.#initialized) {
            return false;
        }
        if (this.#destroyed) {
            throw err(`Cannot initialize destroyed page ${this.#dependencies.pageId}`);
        }
        const generation = this.#generation;
        const completion = createDeferred<boolean>();
        const initialization = completion.promise;
        this.#initializePromise = initialization;
        const operation = (async (): Promise<boolean> => {
            try {
                await command.initializeDomain(parameters, context);
                this.#requireActiveInitialization(generation);
                throwIfAborted(context.signal);
                this.#initialized = true;
                this.#teardown.reset();
                return true;
            } finally {
                if (this.#initializePromise === initialization) this.#initializePromise = null;
            }
        })();
        void operation.then(completion.resolve, (error) => completion.reject(ensureError(error)));
        return await initialization;
    }

    #resetState(): void {
        this.#generation += 1;
        this.#initialized = false;
        this.#destroyed = false;
        this.#teardown.reset();
        this.#initializePromise = null;
    }

    cancel(reason: string): void {
        this.#dependencies.resources.seal();
        this.#generation += 1;
        const listenersController = this.#listenersScope.controller;
        const runtimeTask = this.#runtime.currentTask;
        const detachedScopes = [...this.#detachedScopes.values()];
        this.#detachedScopes.clear();
        this.#initializeScope.abort(reason);
        this.#activation.cancel();
        if (this.#listenersScope.controller === listenersController) this.abortListeners(reason);
        if (this.#runtime.currentTask === runtimeTask) this.#runtime.cancel(reason);
        for (const scope of detachedScopes) scope.abort(reason);
    }

    deferActivation(): void {
        this.#activation.defer();
    }

    activate(): void {
        this.#activation.activate();
    }

    async hide(onCancel: () => void, onHide: () => Promise<void>): Promise<void> {
        if (this.#hideTask) {
            if (this.#transitionCallbackDepth === 0) await this.#hideTask;
            return;
        }
        if (this.#destroyTask) throw new LifecycleCancellationError(`${this.#dependencies.pageId} hide rejected during destruction`, 'page-destroying');
        const completion = createDeferred<void>();
        const task = completion.promise;
        this.#hideTask = task;
        const operation = this.#invokeTransitionCallback(async (): Promise<void> => {
            this.cancel('hide');
            onCancel();
            await this.settleInitialization();
            await this.run('hide', () => this.#invokeTransitionCallback(onHide));
        });
        void operation.then(completion.resolve, (error) => completion.reject(ensureError(error)));
        try {
            await task;
        } finally {
            if (this.#hideTask === task) this.#hideTask = null;
        }
    }

    async settleInitialization(): Promise<void> {
        const tasks = new Set<PageInitializationTask>();
        if (this.#initializeTask) tasks.add(this.#initializeTask);
        if (this.#initializePromise) tasks.add(this.#initializePromise);
        await Promise.all([...tasks].map((task) => this.#settleInitialization(task)));
        await this.#runtime.settle();
    }

    beginListeners(): AbortSignal {
        return this.#listenersScope.begin().signal;
    }

    get listenersController(): AbortController | null {
        return this.#listenersScope.controller;
    }

    abortListeners(reason = 'cleanup'): void {
        this.#listenersScope.abort(reason);
    }

    scheduleReload(): void {
        const location = getLocation();
        if (!isFunction(location.reload)) throw err('Location reload missing');
        getRequestAnimationFrame()(() => location.reload());
    }

    setup(): void {
        runBasePageStandardSetup(this.#dependencies.layout);
    }

    async refresh(parameters: JsonObject | null, command: PageRefreshCommand, context: { signal?: AbortSignal } = {}): Promise<void> {
        this.#abortDetached('refresh');
        await refreshBasePageLifecycle(this.#dependencies, command, parameters, context);
    }

    async destroy(command: PageDestroyCommand): Promise<boolean> {
        if (this.#destroyed) return false;
        if (this.#destroyTask) {
            if (this.#transitionCallbackDepth > 0) return false;
            await this.#destroyTask;
            return false;
        }
        const completion = createDeferred<boolean>();
        const task = completion.promise;
        this.#destroyTask = task;
        const operation = this.#invokeTransitionCallback(() => this.#runDestroy(command));
        void operation.then(completion.resolve, (error) => completion.reject(ensureError(error)));
        try {
            return await task;
        } finally {
            if (this.#destroyTask === task && this.#destroyed) this.#destroyTask = null;
        }
    }

    async #runDestroy(command: PageDestroyCommand): Promise<boolean> {
        this.#generation += 1;
        this.#initializeScope.abort('destroy');
        this.#runtime.cancel('destroy');
        if (this.#hideTask) await this.#settleInitialization(this.#hideTask);
        await this.settleInitialization();
        await this.#teardown.destroyOwnedState({ ...command, onDestroy: () => this.#invokeTransitionCallback(() => command.onDestroy()) });
        this.#destroyed = true;
        this.#initialized = false;
        this.#initializePromise = null;
        return true;
    }

    async cleanup(cleanupDomainState: () => void, onCollectionStateCleaned: () => void): Promise<boolean> {
        return this.#teardown.cleanup(cleanupDomainState, onCollectionStateCleaned);
    }

    #invokeTransitionCallback<Result>(callback: () => Result): Result {
        this.#transitionCallbackDepth += 1;
        try {
            return callback();
        } finally {
            this.#transitionCallbackDepth -= 1;
        }
    }

    #abortDetached(reason: string): void {
        const scopes = [...this.#detachedScopes.values()];
        this.#detachedScopes.clear();
        for (const scope of scopes) {
            scope.abort(reason);
        }
    }

    #requireActiveInitialization(generation: number): void {
        if (generation !== this.#generation || this.#destroyTask || this.#destroyed) {
            throw new LifecycleCancellationError(`${this.#dependencies.pageId} initialization cancelled during lifecycle transition`, 'page-initialization');
        }
    }

    async #settleInitialization(task: PageInitializationTask): Promise<void> {
        try {
            await task;
        } catch (error) {
            if (!isLifecycleCancellationError(error) && !isAbortError(error)) {
                errorHandler.debug(this.#dependencies.pageId, 'Initialization failure settled during lifecycle transition', ensureError(error));
            }
        }
    }
}

export { PageLifecycle };
export interface PageLifecycleOwnerHost {
    pageLifecycle: PageLifecycle;
}
