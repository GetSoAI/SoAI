/* SoAI - Shared pagehost service [frontend/assets/ts/core/pagehost/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler, type ErrorHandler } from '@core/errorHandler.ts';
import { CLEANUP_METHODS } from '@core/pagehost/constants.ts';
import { commitPreparedPageContainer, createPreparedPageContainer, prepareContainer, prepareInstance, resolveContainer, resolveDom, runCleanupMethods } from '@core/pagehost/actions.ts';
import { isPageRegistry } from '@core/pagehost/guards.ts';
import type { CleanupRunner, CurrentPageState, DestroyOptions, PageHostDomApi, PageHostOptions, PageInstance, PageMeta, PageRegistry, PreparedPageState, WhenReadyOptions } from '@core/pagehost/types.ts';
import { isFunction, isHTMLElement } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

class PageHost {
    #registry: PageRegistry | null = null;
    container: HTMLElement | null = null;
    #current: CurrentPageState | null = null;
    #prepared: PreparedPageState | null = null;
    #activeToken: symbol | null = null;
    #cancelledCurrent: PageInstance | null = null;
    #errorHandler: ErrorHandler;
    #domResolver: () => PageHostDomApi | null;
    #cleanupRunner: CleanupRunner;

    constructor({ registry = null, container = null, domResolver = resolveDom, errorHandler: hostErrorHandler = errorHandler, cleanupRunner }: PageHostOptions = {}) {
        this.#errorHandler = hostErrorHandler;
        this.#domResolver = isFunction(domResolver) ? domResolver : resolveDom;
        const defaultCleanupRunner: CleanupRunner = async (instance: PageInstance, methods): Promise<void> => {
            await runCleanupMethods(instance, methods, this.#errorHandler);
        };
        this.#cleanupRunner = isFunction(cleanupRunner) ? cleanupRunner : defaultCleanupRunner;
        if (registry !== null) {
            if (!isPageRegistry(registry)) {
                throw new Error('PageHost requires a valid page registry');
            }
            this.#setRegistry(registry);
        }
        if (container) {
            this.#setContainer(container);
        }
    }

    setRegistry(registry: PageRegistry): this {
        return this.#setRegistry(registry);
    }

    #setRegistry(registry: PageRegistry): this {
        if (!isFunction(registry.create)) {
            throw new Error('PageHost requires a valid page registry');
        }
        this.#registry = registry;
        return this;
    }

    setContainer(container: HTMLElement | string): this {
        return this.#setContainer(container);
    }

    #setContainer(container: HTMLElement | string): this {
        const resolved = resolveContainer(container, this.#domResolver);
        if (!resolved) {
            throw new Error('PageHost requires a valid container element');
        }
        this.container = resolved;
        return this;
    }

    getContainer(): HTMLElement | null {
        return this.container;
    }

    getCurrent(): { name: string; instance: PageInstance } | null {
        if (!this.#current) {
            return null;
        }
        return { name: this.#current.name, instance: this.#current.instance };
    }

    whenReady(options: WhenReadyOptions = {}): Promise<void> {
        const page = this.#prepared ?? this.#current;
        if (!page) return Promise.resolve();
        if (options.waitForReveal === false) {
            return page.preparedPromise;
        }
        if (options.waitForData === true) {
            return page.dataReadyPromise;
        }
        return page.viewReadyPromise;
    }

    allowReveal(): void {
        const instance = this.#current?.instance ?? null;
        if (instance?.pageLifecycle) {
            instance.pageLifecycle.allowReveal();
        }
    }

    async prepare(name: string, parameters: JsonObject = {}): Promise<PageInstance | null> {
        if (!name) {
            throw new Error('PageHost.prepare requires a page name');
        }
        const container = this.container;
        if (!isHTMLElement(container)) {
            throw new Error('PageHost requires a container before mounting pages');
        }
        const registry = this.#requireRegistry();
        const meta = registry.getMeta(name);
        if (!meta) {
            throw new Error(`Page "${name}" is not registered`);
        }
        this.cancelPrepared('superseded');
        const token = Symbol(name);
        const preparedContainer = createPreparedPageContainer(container);
        prepareContainer(preparedContainer, name, this.#domResolver);
        const instance = registry.create(name);
        if (!instance) {
            throw new Error(`Failed to create page instance "${name}"`);
        }
        const prepared: PreparedPageState = {
            name,
            instance,
            meta,
            token,
            container: preparedContainer,
            preparedPromise: Promise.resolve(),
            viewReadyPromise: Promise.resolve(),
            dataReadyPromise: Promise.resolve(),
            isPreparationComplete: false
        };
        try {
            prepareInstance(instance, preparedContainer);
        } catch (error) {
            this.#discardPreparedPage(prepared, 'prepare-container-failed');
            throw ensureError(error);
        }
        this.#activeToken = token;
        this.#prepared = prepared;
        try {
            instance.pageLifecycle?.deferActivation();
            await this.#initializePreparedPage(prepared, parameters);
            if (this.#activeToken !== token) {
                return null;
            }
            return instance;
        } catch (error) {
            const runtimeError = ensureError(error);
            if (this.#activeToken !== token) return null;
            this.#activeToken = null;
            this.#prepared = null;
            this.#discardPreparedPage(prepared, 'prepare-failed');
            throw runtimeError;
        }
    }

    async commitPrepared(): Promise<PageInstance | null> {
        const prepared = this.#prepared;
        const container = this.container;
        if (!prepared || !prepared.isPreparationComplete || this.#activeToken !== prepared.token) return null;
        if (!isHTMLElement(container)) throw new Error('PageHost requires a container before committing a prepared page');
        const previous = this.#current;
        const previousContainer = commitPreparedPageContainer(container, prepared.container);
        if (previous) prepareInstance(previous.instance, previousContainer);
        prepareInstance(prepared.instance, container);
        this.#current = { ...prepared, container };
        this.#cancelledCurrent = null;
        this.#prepared = null;
        if (previous) {
            await this.#teardownPage(previous, { swallowErrors: true, reason: 'navigation-commit' });
        }
        if (this.#current?.instance === prepared.instance && this.#cancelledCurrent !== prepared.instance) {
            prepared.instance.pageLifecycle?.activate();
        }
        return prepared.instance;
    }

    async destroyCurrent({ force = false, reason = 'teardown' }: DestroyOptions = {}): Promise<void> {
        this.cancelPrepared(reason);
        const current = this.#current;
        this.#activeToken = null;
        this.#current = null;
        this.#cancelledCurrent = null;
        if (current) await this.#teardownPage(current, { swallowErrors: force, reason });
    }

    cancelCurrent(expectedInstance: PageInstance, reason: string = 'cancelled'): boolean {
        const current = this.#current;
        if (!current || current.instance !== expectedInstance) return false;
        this.#cancelledCurrent = current.instance;
        this.#cancelInstance(current.instance, reason);
        return true;
    }

    cancelPrepared(reason: string = 'cancelled'): void {
        const active = this.#prepared;
        this.#activeToken = null;
        this.#prepared = null;
        if (active) this.#discardPreparedPage(active, reason);
    }

    #cancelInstance(instance: PageInstance, reason: string): void {
        const abortController = instance['abortController'];
        if (abortController instanceof AbortController) {
            try {
                abortController.abort(reason);
            } catch (error) {
                const runtimeError = ensureError(error);
                this.#errorHandler.debug('PageHost', 'Abort controller cancel failed', runtimeError);
            }
        }
        if (isFunction(instance.cancel)) {
            try {
                instance.cancel(reason);
            } catch (error) {
                const runtimeError = ensureError(error);
                this.#errorHandler.debug('PageHost', 'Page cancel failed', runtimeError);
            }
        }
    }

    #initializePreparedPage = async (prepared: PreparedPageState, parameters: JsonObject): Promise<void> => {
        const { instance, token } = prepared;
        if (!isFunction(instance.initialize)) {
            throw new Error('Page instance missing initialize method');
        }
        await Promise.resolve(instance.initialize(parameters));
        if (this.#activeToken !== token) {
            return;
        }
        let preparedTask: Promise<void> = Promise.resolve();
        let viewReadyTask: Promise<void> = Promise.resolve();
        let dataReadyTask: Promise<void> = Promise.resolve();
        if (instance.pageLifecycle) {
            preparedTask = Promise.resolve(instance.pageLifecycle.whenReady({ waitForReveal: false }));
            viewReadyTask = Promise.resolve(instance.pageLifecycle.whenReady({ waitForData: false }));
            dataReadyTask = Promise.resolve(instance.pageLifecycle.whenReady({ waitForData: true }));
        }
        prepared.preparedPromise = preparedTask;
        prepared.viewReadyPromise = viewReadyTask;
        prepared.dataReadyPromise = dataReadyTask;
        prepared.isPreparationComplete = true;
    };

    #discardPreparedPage(prepared: PreparedPageState, reason: string): void {
        void this.#teardownPage(prepared, { swallowErrors: true, reason }).catch((error) => {
            this.#errorHandler.warn('PageHost', `Discard failed for prepared page ${prepared.name}`, ensureError(error));
        });
    }

    #teardownPage = async (page: CurrentPageState, { swallowErrors, reason }: { swallowErrors: boolean; reason: string }): Promise<void> => {
        const { instance, name } = page;
        const teardownErrors: Error[] = [];
        this.#cancelInstance(instance, reason);
        if (isFunction(instance.hide)) {
            try {
                await instance.hide();
            } catch (error) {
                const runtimeError = ensureError(error);
                teardownErrors.push(runtimeError);
                if (swallowErrors) {
                    this.#errorHandler.warn('PageHost', `Hide failed for page ${name}`, runtimeError);
                }
            }
        }
        try {
            await this.#cleanupRunner(instance, CLEANUP_METHODS);
        } catch (error) {
            const runtimeError = ensureError(error);
            teardownErrors.push(runtimeError);
            if (swallowErrors) {
                this.#errorHandler.debug('PageHost', `Cleanup failed for page ${name}`, runtimeError);
            }
        }
        if (teardownErrors.length > 0 && !swallowErrors) {
            throw new AggregateError(teardownErrors, `Failed to teardown page ${name}`);
        }
    };

    #requireRegistry = (): PageRegistry => {
        if (!this.#registry) {
            throw new Error('PageHost requires a page registry');
        }
        return this.#registry;
    };
}

export { PageHost };
export type { CleanupRunner, CurrentPageState, DestroyOptions, PageHostDomApi, PageHostOptions, PageInstance, PageMeta, PageRegistry, PreparedPageState, WhenReadyOptions };
