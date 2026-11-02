/* SoAI - Shared pagehost service [frontend/assets/ts/core/pagehost/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { EventBus } from '@core/EventBus.ts';
import { errorHandler, type ErrorHandler } from '@core/errorHandler.ts';
import { PageDisposal } from '@core/pagehost/disposal.ts';
import { commitPreparedPageContainer, initializePreparedPage, createPreparedPageContainer, PageContainerRollbackError, prepareContainer, prepareInstance, resolveContainer, resolveDom, runCleanupMethods } from '@core/pagehost/actions.ts';
import { isPageRegistry } from '@core/pagehost/guards.ts';
import type { CleanupRunner, CurrentPageState, DestroyOptions, PageHostCancellation, PageHostCommitOptions, PageHostDomApi, PageHostOptions, PageHostPrepareOptions, PageInstance, PageMeta, PageRegistry, PreparedPageState, WhenReadyOptions, PageHostOwnership } from '@core/pagehost/types.ts';
import { runCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';
import { isFunction, isHTMLElement } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { throwIfAborted } from '@core/errors/abort.ts';
import type { PageMountScope } from '@core/routing/router/types.ts';

class PageHost {
    #registry: PageRegistry | null = null;
    container: HTMLElement | null = null;
    #current: CurrentPageState | null = null;
    #prepared: PreparedPageState | null = null;
    #activeToken: symbol | null = null;
    #cancelledCurrent: PageInstance | null = null;
    #errorHandler: ErrorHandler;
    #domResolver: () => PageHostDomApi | null;
    readonly #disposal: PageDisposal;
    #commitCompletion: Promise<void> | null = null;

    constructor({ registry = null, container = null, domResolver = resolveDom, errorHandler: hostErrorHandler = errorHandler, cleanupRunner }: PageHostOptions = {}) {
        this.#errorHandler = hostErrorHandler;
        this.#domResolver = isFunction(domResolver) ? domResolver : resolveDom;
        const defaultCleanupRunner: CleanupRunner = async (instance: PageInstance, methods): Promise<void> => {
            await runCleanupMethods(instance, methods, this.#errorHandler);
        };
        this.#disposal = new PageDisposal(isFunction(cleanupRunner) ? cleanupRunner : defaultCleanupRunner);
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

    getOwnership(): PageHostOwnership {
        return this.#disposal.getOwnership(this.#current, this.#prepared, this.#commitCompletion !== null);
    }

    getCurrentMountScope(): PageMountScope | null {
        return this.#current?.mountScope ?? null;
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

    async prepare(name: string, parameters: JsonObject = {}, { signal, createMountScope }: PageHostPrepareOptions): Promise<PageInstance | null> {
        throwIfAborted(signal);
        if (this.#commitCompletion) await this.#commitCompletion;
        throwIfAborted(signal);
        if (this.#disposal.commitFailure) throw this.#disposal.commitFailure;
        if (!name) {
            throw new Error('PageHost.prepare requires a page name');
        }
        const container = this.container;
        if (!isHTMLElement(container)) {
            throw new Error('PageHost requires a container before mounting pages');
        }
        const registry = this.#registry;
        if (!registry) throw new Error('PageHost requires a page registry');
        const meta = registry.getMeta(name);
        if (!meta) {
            throw new Error(`Page "${name}" is not registered`);
        }
        const token = Symbol(name);
        const predecessor = this.#prepared;
        this.#activeToken = token;
        this.#prepared = null;
        if (predecessor) this.#discardPreparedPage(predecessor, 'superseded');
        await this.#disposal.waitForRelease();
        throwIfAborted(signal);
        if (this.#activeToken !== token) return null;
        const preparedContainer = createPreparedPageContainer(container);
        prepareContainer(preparedContainer, name, this.#domResolver);
        const presentation = new EventBus();
        let mountScope: PageMountScope;
        let instance: PageInstance;
        try {
            mountScope = createMountScope({
                generation: token,
                isCurrent: () => {
                    const ownsPreparation = this.#activeToken === token && this.#current?.token !== token;
                    const ownsCommittedMount = this.#current?.token === token && this.#cancelledCurrent !== this.#current.instance;
                    return ownsPreparation || ownsCommittedMount;
                },
                isCommitted: () => this.#current?.token === token,
                isActive: () => this.#current?.token === token && this.#current.isActivated && this.#cancelledCurrent !== this.#current.instance,
                subscribe: (listener) => presentation.on('changed', () => listener())
            });
            if (this.#activeToken !== token) {
                presentation.emit('changed');
                return null;
            }
            const created = registry.create(name, mountScope);
            if (!created) throw new Error(`Failed to create page instance "${name}"`);
            instance = created;
        } catch (error) {
            if (this.#activeToken === token) this.#activeToken = null;
            presentation.emit('changed');
            throw error;
        }
        const prepared: PreparedPageState = {
            name,
            instance,
            meta,
            token,
            mountScope,
            presentation,
            isActivated: false,
            container: preparedContainer,
            preparedPromise: Promise.resolve(),
            viewReadyPromise: Promise.resolve(),
            dataReadyPromise: Promise.resolve(),
            isPreparationComplete: false,
            releaseMutationAdmission: null
        };
        if (this.#activeToken !== token) {
            this.#discardPreparedPage(prepared, 'superseded');
            return null;
        }
        this.#prepared = prepared;
        try {
            prepareInstance(instance, preparedContainer);
            if (this.#activeToken !== token) return null;
            instance.pageLifecycle?.deferActivation();
            if (this.#activeToken !== token) return null;
            await initializePreparedPage(prepared, parameters, () => this.#activeToken === token);
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

    async commitPrepared({ signal, finalAdmission, mountPublication, afterCommit }: PageHostCommitOptions = {}): Promise<PageInstance | null> {
        if (this.#commitCompletion) await this.#commitCompletion;
        if (this.#disposal.commitFailure) throw this.#disposal.commitFailure;
        const prepared = this.#prepared;
        const container = this.container;
        if (!prepared || !prepared.isPreparationComplete || this.#activeToken !== prepared.token) return null;
        if (!isHTMLElement(container)) throw new Error('PageHost requires a container before committing a prepared page');
        const completion = createDeferred<void>();
        this.#commitCompletion = completion.promise;
        const previous = this.#current;
        const releaseCommitOwnership = this.#disposal.captureCommit(previous, prepared);
        try {
            throwIfAborted(signal);
            finalAdmission?.();
            throwIfAborted(signal);
            if (previous) previous.releaseMutationAdmission = previous.mountScope.admission.blockMutations();
            const previousCancellation = this.#cancelledCurrent;
            const previousContainer = commitPreparedPageContainer(container, prepared.container, {
                previous: previous?.instance ?? null,
                incoming: prepared.instance,
                commit: () => {
                    this.#current = { ...prepared, container };
                    this.#cancelledCurrent = null;
                    this.#prepared = null;
                    mountPublication?.commit();
                },
                rollback: () => {
                    this.#current = previous;
                    this.#cancelledCurrent = previousCancellation;
                    this.#prepared = prepared;
                    mountPublication?.rollback();
                }
            });
            await this.#disposal.settleCommit(previous, previousContainer, afterCommit);
            if (this.#current?.instance === prepared.instance && this.#cancelledCurrent !== prepared.instance && prepared.mountScope.admission.isCurrent()) {
                this.#current.isActivated = true;
                prepared.instance.pageLifecycle?.activate();
                prepared.presentation.emit('changed');
            }
            return prepared.instance;
        } catch (error) {
            if (error instanceof PageContainerRollbackError)
                this.#disposal.retainFailedCommit(
                    error,
                    [previous, prepared].filter((page): page is CurrentPageState => page !== null)
                );
            else if (previous && this.#current?.instance !== prepared.instance) {
                previous.releaseMutationAdmission?.();
                previous.releaseMutationAdmission = null;
            }
            throw error;
        } finally {
            releaseCommitOwnership();
            this.#commitCompletion = null;
            completion.resolve(undefined);
        }
    }

    async destroyCurrent({ expectedInstance, reason = 'teardown' }: DestroyOptions = {}): Promise<void> {
        if (this.#commitCompletion) await this.#commitCompletion;
        if (this.#disposal.commitFailure) throw this.#disposal.commitFailure;
        const current = this.#current;
        if (expectedInstance) {
            if (current?.instance !== expectedInstance) return;
            this.#current = null;
            this.#cancelledCurrent = null;
            await this.#disposal.dispose(current, reason);
            return;
        }
        const prepared = this.#prepared;
        this.#activeToken = null;
        this.#prepared = null;
        this.#current = null;
        this.#cancelledCurrent = null;
        const releases = [prepared, current].filter((page): page is CurrentPageState => page !== null).map((page) => this.#disposal.dispose(page, reason));
        await Promise.allSettled(releases);
        await this.#disposal.waitForRelease();
    }

    cancelCurrent(expectedInstance: PageInstance, reason: string = 'cancelled'): boolean {
        const current = this.#current;
        if (!current || current.instance !== expectedInstance) return false;
        this.#cancelledCurrent = current.instance;
        try {
            this.#disposal.cancelInstance(current.instance, reason);
        } finally {
            current.presentation.emit('changed');
        }
        return true;
    }

    cancelPrepared(reason: string = 'cancelled'): void {
        if (this.#disposal.commitFailure || this.#commitCompletion) return;
        const active = this.#prepared;
        this.#activeToken = null;
        this.#prepared = null;
        if (active) this.#discardPreparedPage(active, reason);
    }

    captureCancellation(reason: string, scope: 'all' | 'prepared' = 'all'): PageHostCancellation {
        const current = scope === 'all' ? this.#current : null;
        const prepared = this.#prepared;
        const token = this.#activeToken;
        const pages = [current, prepared].filter((page): page is CurrentPageState => page !== null);
        return {
            seal: () => this.#disposal.sealResources(pages),
            cancel: () => {
                const failures: Error[] = [];
                if (current) runCleanupStepCollectingFailure(() => this.cancelCurrent(current.instance, reason), failures);
                if (this.#prepared === prepared && this.#activeToken === token) runCleanupStepCollectingFailure(() => this.cancelPrepared(reason), failures);
                throwCollectedCleanupFailures(failures);
            }
        };
    }

    #discardPreparedPage(prepared: PreparedPageState, reason: string): void {
        void this.#disposal.dispose(prepared, reason).catch((error) => {
            this.#errorHandler.warn('PageHost', `Discard failed for prepared page ${prepared.name}`, ensureError(error));
        });
    }
}

export { PageHost };
export type { CleanupRunner, CurrentPageState, DestroyOptions, PageHostDomApi, PageHostOptions, PageInstance, PageMeta, PageRegistry, PreparedPageState, WhenReadyOptions };
