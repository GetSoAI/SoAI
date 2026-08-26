/* SoAI - Shared component support registry [frontend/assets/ts/core/componentsupport/registry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction, isObject } from '@core/typeGuards.ts';
import type { ComponentInstance, ComponentMeta, RegistryOptions } from '@core/componentsupport/types.ts';

type Registry = Readonly<{
    force?: boolean;
}>;

const DEFAULT_REGISTRY_OPTIONS: Readonly<Required<RegistryOptions>> = Object.freeze({
    autoInitialize: false,
    priority: 0
});

interface InitializableComponent {
    initialize: () => Promise<void> | void;
}

interface DestroyableComponent {
    destroy: () => Promise<void> | void;
}

const isInitializableComponent = (value: ComponentInstance): value is ComponentInstance & InitializableComponent => {
    return isObject(value) && 'initialize' in value && isFunction(value.initialize);
};

const isDestroyableComponent = (value: ComponentInstance): value is ComponentInstance & DestroyableComponent => {
    return isObject(value) && 'destroy' in value && isFunction(value.destroy);
};

class ComponentRegistry {
    components: Map<string, ComponentMeta>;

    constructor() {
        this.components = new Map();
    }

    register(name: string, component: ComponentInstance | null | undefined, options: RegistryOptions = {}): ComponentInstance {
        const identifier = typeof name === 'string' ? name.trim() : '';
        if (!identifier) {
            throw new Error('ComponentRegistry.register requires a non-empty component name');
        }
        if (component === null || component === undefined) {
            throw new Error(`ComponentRegistry.register("${identifier}") requires a component instance`);
        }
        if (this.components.has(identifier)) {
            throw new Error(`Component "${identifier}" is already registered`);
        }

        const meta: ComponentMeta = {
            component,
            options: { ...DEFAULT_REGISTRY_OPTIONS, ...options },
            initialized: false,
            initializing: false,
            initialization: null
        };

        if (meta.options.autoInitialize) {
            throw new Error(`Component "${identifier}" cannot use autoInitialize; initialize it explicitly during bootstrap`);
        }

        this.components.set(identifier, meta);
        return meta.component;
    }

    async initialize(name: string, { force = false }: Registry = {}): Promise<void> {
        const meta = this.components.get(name);
        if (!meta) {
            throw new Error(`Component "${name}" is not registered`);
        }

        if (!force && meta.initialization) {
            await meta.initialization;
            return;
        }
        if (!force && meta.initialized) {
            return;
        }

        const { component } = meta;
        if (!isInitializableComponent(component)) {
            throw new Error(`Component "${name}" must expose initialize()`);
        }

        if (force && meta.initialization) {
            await meta.initialization;
        }
        if (force && meta.initialized) {
            await this.destroy(name);
        }

        meta.initializing = true;
        const pending = (async (): Promise<void> => {
            await component.initialize();
            meta.initialized = true;
        })();
        const tracked = pending.finally(() => {
            if (meta.initialization === tracked) {
                meta.initialization = null;
            }
            meta.initializing = false;
        });
        meta.initialization = tracked;
        await tracked;
    }

    async initializeAll({ force = false }: Registry = {}): Promise<void> {
        const entries = Array.from(this.components.entries()).sort(([, firstValue], [, secondValue]) => firstValue.options.priority - secondValue.options.priority);
        for (const [name] of entries) {
            await this.initialize(name, { force });
        }
    }

    async destroy(name: string): Promise<void> {
        const meta = this.components.get(name);
        if (!meta) {
            return;
        }
        if (meta.initialization) {
            await meta.initialization;
        }
        if (!meta.initialized) {
            return;
        }

        const { component } = meta;

        if (isDestroyableComponent(component)) {
            await component.destroy();
        }

        meta.initialized = false;
    }

    async destroyAll(): Promise<void> {
        const entries = Array.from(this.components.keys()).reverse();
        for (const name of entries) {
            await this.destroy(name);
        }
    }

    get(name: string): ComponentInstance | undefined {
        return this.components.get(name)?.component;
    }

    isInitialized(name: string): boolean {
        return this.components.get(name)?.initialized ?? false;
    }

    reset(name: string): void {
        const meta = this.components.get(name);
        if (meta) {
            meta.initialized = false;
            meta.initializing = false;
            meta.initialization = null;
        }
    }

    resetAll(): void {
        this.components.forEach((meta) => {
            meta.initialized = false;
            meta.initializing = false;
            meta.initialization = null;
        });
    }
}

export { DEFAULT_REGISTRY_OPTIONS, ComponentRegistry };
