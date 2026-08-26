/* SoAI - Frontend application layout shell [frontend/assets/ts/app/bootstrap/LayoutShell.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { markRegistryInitialized, markRegistryInitializing, markRegistryReset, resolveLayoutShellComponent } from '@app/bootstrap/layoutshell/actions.ts';
import { initializeLayoutShellComponent } from '@app/bootstrap/layoutshell/effects.ts';
import { assertDestroyableComponent, assertLayoutShellDependencies } from '@app/bootstrap/layoutshell/guards.ts';
import { createLayoutShellComponentSpec, createLayoutShellState, findLayoutShellDescriptor } from '@app/bootstrap/layoutshell/state.ts';
import type { ComponentDescriptor, ComponentInstance, InitializeOptions, LayoutShellDependencies, LayoutShellState } from '@app/bootstrap/layoutshell/types.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isFunction } from '@core/typeGuards.ts';
import { coerceErrorMessage, ensureError } from '@core/errors/coerce.ts';

class LayoutShell {
    #state: LayoutShellState;
    #componentSpec: ComponentDescriptor[];
    #dependencies: LayoutShellDependencies;

    constructor(dependencies: LayoutShellDependencies) {
        assertLayoutShellDependencies(dependencies);
        this.#state = createLayoutShellState();
        this.#componentSpec = createLayoutShellComponentSpec();
        this.#dependencies = dependencies;
    }

    get initialized(): boolean {
        return this.#state.initialized;
    }

    #markRegistryInitialized(descriptor: ComponentDescriptor, instance: ComponentInstance): void {
        markRegistryInitialized(this.#dependencies.componentRegistry, descriptor, instance);
    }

    #markRegistryInitializing(descriptor: ComponentDescriptor, instance: ComponentInstance): void {
        markRegistryInitializing(this.#dependencies.componentRegistry, descriptor, instance);
    }

    #markRegistryReset(descriptor: ComponentDescriptor, instance: ComponentInstance): void {
        markRegistryReset(this.#dependencies.componentRegistry, descriptor, instance);
    }

    resolveComponent(descriptor: ComponentDescriptor): ComponentInstance {
        return resolveLayoutShellComponent(descriptor, this.#dependencies.mainStatusMonitor, this.#dependencies.componentLookup);
    }

    async #initializeComponent(descriptor: ComponentDescriptor, instance: ComponentInstance, options: InitializeOptions): Promise<void> {
        await initializeLayoutShellComponent(descriptor, instance, options, {
            onInitializing: () => this.#markRegistryInitializing(descriptor, instance),
            onInitialized: () => this.#markRegistryInitialized(descriptor, instance),
            onReset: () => this.#markRegistryReset(descriptor, instance),
            onActivate: () => {
                this.#state.active.set(descriptor.key, instance);
            }
        });
    }

    async initialize(options: InitializeOptions = {}): Promise<boolean> {
        if (this.#state.bootPromise && !options.force) {
            return this.#state.bootPromise;
        }
        const execute = async (): Promise<boolean> => {
            if (options.force) {
                await this.teardown();
            }
            const mainStatusDescriptor = findLayoutShellDescriptor(this.#componentSpec, 'mainStatusMonitor');
            if (!mainStatusDescriptor) {
                throw new Error('MainStatusMonitor descriptor is required');
            }
            const mainStatusInstance = this.resolveComponent(mainStatusDescriptor);
            await this.#initializeComponent(mainStatusDescriptor, mainStatusInstance, options);

            for (const descriptor of this.#componentSpec) {
                if (descriptor.key === 'mainStatusMonitor') {
                    continue;
                }
                const instance = this.resolveComponent(descriptor);
                try {
                    await this.#initializeComponent(descriptor, instance, options);
                } catch (error) {
                    const runtimeError = ensureError(error);
                    if (descriptor.required) {
                        errorHandler.error('LayoutShell', `Component initialization failed for ${descriptor.key}`, runtimeError);
                        this.#markRegistryReset(descriptor, instance);
                        throw runtimeError;
                    }
                    errorHandler.warn('LayoutShell', `Optional component initialization failed for ${descriptor.key}`, runtimeError);
                    this.#markRegistryReset(descriptor, instance);
                }
            }

            this.#state.initialized = true;
            errorHandler.info('LayoutShell', 'Layout shell initialized', {
                components: Array.from(this.#state.active.keys())
            });
            return true;
        };

        const promise = execute().catch((error) => {
            this.#state.bootPromise = null;
            const runtimeError = ensureError(error);
            errorHandler.error('LayoutShell', 'Boot execution failed', runtimeError);
            throw runtimeError;
        });
        this.#state.bootPromise = promise;
        return promise;
    }

    async teardown(): Promise<void> {
        if (!this.#state.active.size) {
            this.#state.initialized = false;
            this.#state.bootPromise = null;
            return;
        }

        const tasks: Promise<void>[] = [];
        const reversedDescriptors = Array.from(this.#componentSpec).reverse();
        for (const descriptor of reversedDescriptors) {
            const instance = this.#state.active.get(descriptor.key);
            if (!instance) {
                continue;
            }
            if (descriptor.key === 'mainStatusMonitor') {
                if (isFunction(instance.disconnect)) {
                    instance.disconnect();
                }
                this.#state.active.delete(descriptor.key);
                this.#markRegistryReset(descriptor, instance);
                continue;
            }
            const destroy = instance.destroy;
            if (!instance || !isFunction(destroy)) {
                throw new Error(`Layout shell component ${descriptor.key} does not expose destroy`);
            }
            assertDestroyableComponent(descriptor, instance);
            const task = (async (): Promise<void> => {
                try {
                    const result = instance.destroy();
                    await result;
                } catch (error) {
                    const message = coerceErrorMessage(error, 'unknown error');
                    throw new Error(`Component destroy failed for ${descriptor.key}: ${message}`);
                }
            })();
            tasks.push(task);
            this.#state.active.delete(descriptor.key);
            this.#markRegistryReset(descriptor, instance);
        }

        this.#state.initialized = false;
        this.#state.bootPromise = null;
        if (tasks.length) {
            await Promise.all(tasks);
        }
    }

    get(key: string): ComponentInstance {
        if (!key) {
            throw new Error('LayoutShell get requires a key');
        }
        const existing = this.#state.active.get(key);
        if (existing) {
            return existing;
        }
        const descriptor = findLayoutShellDescriptor(this.#componentSpec, key);
        if (!descriptor) {
            throw new Error(`Layout shell component ${key} unavailable`);
        }
        const instance = this.resolveComponent(descriptor);
        this.#state.active.set(key, instance);
        return instance;
    }
}

export { LayoutShell };
export type { ComponentInstance, InitializeOptions, LayoutShellDependencies };
