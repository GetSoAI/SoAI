/* SoAI - Routed page runtime readiness, cancellation, and listener-scope ownership [frontend/assets/ts/core/routing/pages/basepage/PageLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getLocation, getRequestAnimationFrame } from '@core/environment/public.ts';
import { ErrorBoundary } from '@core/ErrorBoundary.ts';
import { LifecycleScope } from '@core/lifecycle/lifecycleScope.ts';
import { err, requestFunctionValue } from '@core/routing/pages/basepagecore/actions.ts';
import { initializeBasePageLifecycle, runBasePageStandardSetup } from '@core/routing/pages/basepage/service.ts';
import { PageTeardown } from '@core/routing/pages/basepage/PageTeardown.ts';
import { PageRuntime } from '@core/runtime/PageRuntime.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { PageDestroyCommand, PageInitializationCommand, PageLifecycleDependencies, PageRefreshCommand } from '@core/routing/pages/basepage/pageLifecycleContracts.ts';
import { isFunction } from '@core/typeGuards.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { LifecycleCancellationError, isLifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { PageActivationGate } from '@core/routing/pages/basepage/PageActivationGate.ts';

type PageInitializationTask = Promise<boolean | void>;

class PageLifecycle {
    readonly #dependencies: PageLifecycleDependencies;
    readonly #runtime: PageRuntime;
    readonly #boundary: ErrorBoundary;
    readonly #teardown: PageTeardown;
    readonly #initializeScope = new LifecycleScope();
    readonly #listenersScope = new LifecycleScope();
    readonly #activation = new PageActivationGate();
    #initialized = false;
    #destroyed = false;
    #destroying = false;
    #initializePromise: Promise<boolean> | null = null;
    #initializeTask: Promise<void> | null = null;
    #destroyTask: Promise<boolean> | null = null;
    #hideTask: Promise<void> | null = null;
    #initializeSequence = 0;
    #generation = 0;

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

    runDetached(operation: string, task: () => Promise<void> | void): void {
        void this.#boundary.execute(task, operation).catch((error) => {
            errorHandler.debug(this.#dependencies.pageId, `Detached operation rejection settled: ${operation}`, ensureError(error));
        });
    }

    async initialize(parameters: JsonObject | undefined, command: PageInitializationCommand): Promise<void> {
        if (this.#destroying || this.#destroyTask) throw new LifecycleCancellationError(`${this.#dependencies.pageId} initialization rejected during destruction`, 'page-destroying');
        if (this.#hideTask) throw new LifecycleCancellationError(`${this.#dependencies.pageId} initialization rejected during hide`, 'page-hiding');
        const previousTask = this.#initializeTask;
        const sequence = ++this.#initializeSequence;
        const initializeRun = this.#initializeScope.begin('reinitialize');
        let task!: Promise<void>;
        task = (async (): Promise<void> => {
            if (previousTask) await this.#settleInitialization(previousTask);
            if (sequence !== this.#initializeSequence || initializeRun.signal.aborted) return;
            await initializeBasePageLifecycle(
                {
                    pageId: this.#dependencies.pageId,
                    runtime: this.#runtime,
                    phases: this.#activation.phases(command.readiness),
                    pageHost: this.#dependencies.pageHost,
                    pageDom: this.#dependencies.pageDom,
                    services: this.#dependencies.services,
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
        this.#initializeTask = task;
        try {
            await task;
        } finally {
            if (this.#initializeTask === task) this.#initializeTask = null;
            if (this.#initializeScope.isCurrent(initializeRun)) this.#initializeScope.abort('initialize-complete');
        }
    }

    async #initialize(parameters: JsonObject | null, command: PageInitializationCommand, context: { signal?: AbortSignal }): Promise<boolean> {
        if (this.#destroying) throw new LifecycleCancellationError(`${this.#dependencies.pageId} initialization rejected during destruction`, 'page-destroying');
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
        let initialization!: Promise<boolean>;
        initialization = (async (): Promise<boolean> => {
            try {
                await command.initializeDomain(parameters, context);
                this.#requireActiveInitialization(generation);
                this.#initialized = true;
                this.#teardown.reset();
                return true;
            } finally {
                this.#initializePromise = null;
            }
        })();
        this.#initializePromise = initialization;
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
        this.#generation += 1;
        this.#initializeSequence += 1;
        this.#initializeScope.abort(reason);
        this.#activation.cancel();
        this.abortListeners(reason);
        this.#runtime.cancel(reason);
    }

    deferActivation(): void {
        this.#activation.defer();
    }

    activate(): void {
        this.#activation.activate();
    }

    async hide(onCancel: () => void, onHide: () => Promise<void>): Promise<void> {
        if (this.#hideTask) return await this.#hideTask;
        if (this.#destroying || this.#destroyTask) throw new LifecycleCancellationError(`${this.#dependencies.pageId} hide rejected during destruction`, 'page-destroying');
        let task!: Promise<void>;
        task = (async (): Promise<void> => {
            this.cancel('hide');
            onCancel();
            await this.settleInitialization();
            await this.run('hide', onHide);
        })();
        this.#hideTask = task;
        try {
            await task;
        } finally {
            this.#hideTask = null;
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
        runBasePageStandardSetup(this.#dependencies.services, this.#dependencies.layout);
    }

    async refresh(parameters: JsonObject | null, command: PageRefreshCommand, context: { signal?: AbortSignal } = {}): Promise<void> {
        command.beforeCleanup();
        await this.#dependencies.layout.cleanup();
        await this.#dependencies.resources.cleanupTracked();
        const requiredResources = command.getRequiredResources();
        if (requiredResources.length) {
            const streamResources = this.#dependencies.streaming.runtime().resources;
            await this.#dependencies.streaming.ensureReady(streamResources);
            const ensureResourceStarted = requestFunctionValue(streamResources, 'ensureResourceStarted', 'SM');
            await Promise.all(requiredResources.map((name) => Promise.resolve(ensureResourceStarted(name))));
        }
        command.refreshDomainState();
        await command.onInitialize(parameters, context);
    }

    async destroy(command: PageDestroyCommand): Promise<boolean> {
        if (this.#destroyed) return false;
        if (this.#destroyTask) {
            await this.#destroyTask;
            return false;
        }
        const task = this.#runDestroy(command);
        this.#destroyTask = task;
        try {
            return await task;
        } finally {
            this.#destroyTask = null;
        }
    }

    async #runDestroy(command: PageDestroyCommand): Promise<boolean> {
        this.#destroying = true;
        this.#generation += 1;
        this.#initializeSequence += 1;
        this.#initializeScope.abort('destroy');
        this.#runtime.cancel('destroy');
        try {
            if (this.#hideTask) await this.#settleInitialization(this.#hideTask);
            await this.settleInitialization();
            try {
                await command.onDestroy();
            } catch (error) {
                errorHandler.error(this.#dependencies.pageId, 'Page destroy hooks failed', ensureError(error));
            }
            await this.#teardown.destroyOwnedState();
            await this.cleanup(command.cleanupDomainState, command.onCollectionStateCleaned);
            this.#destroyed = true;
            this.#initialized = false;
            this.#initializePromise = null;
            return true;
        } finally {
            this.#destroying = false;
        }
    }

    async cleanup(cleanupDomainState: () => void, onCollectionStateCleaned: () => void): Promise<boolean> {
        return this.#teardown.cleanup(cleanupDomainState, onCollectionStateCleaned);
    }

    #requireActiveInitialization(generation: number): void {
        if (generation !== this.#generation || this.#destroying || this.#destroyed) {
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
