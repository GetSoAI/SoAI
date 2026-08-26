/* SoAI - Frontend application layout shell actions [frontend/assets/ts/app/bootstrap/layoutshell/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { assertNonEmptyString } from '@core/assertions.ts';
import { isArray, isFunction } from '@core/typeGuards.ts';
import type { ComponentRegistry } from '@core/componentsupport/public.ts';
import type { ComponentDescriptor, ComponentInstance } from '@app/bootstrap/layoutshell/types.ts';

const ensureRegistryMetadata = (registry: ComponentRegistry, descriptor: ComponentDescriptor, instance: ComponentInstance): void => {
    if (!registry || !isArray(descriptor.registryNames)) {
        throw new Error('Component registry must expose registryNames arrays');
    }
    const components = registry.components;
    if (!(components instanceof Map)) {
        throw new Error('Component registry must expose a components map');
    }
    if (!descriptor.registryNames.length) {
        return;
    }
    const register = registry.register;
    if (!isFunction(register)) {
        throw new Error('Component registry must expose register');
    }
    descriptor.registryNames.forEach((name) => {
        const normalizedName = assertNonEmptyString(name, 'Registry name');
        if (!components.has(normalizedName)) {
            registry.register(normalizedName, instance, descriptor.registryOptions ?? {});
        }
    });
};

const markRegistryInitialized = (registry: ComponentRegistry, descriptor: ComponentDescriptor, instance: ComponentInstance): void => {
    ensureRegistryMetadata(registry, descriptor, instance);
    const components = registry.components;
    descriptor.registryNames.forEach((name) => {
        const normalizedName = assertNonEmptyString(name, 'Registry name');
        const meta = components.get(normalizedName);
        if (!meta) {
            throw new Error(`Component registry missing metadata for ${normalizedName}`);
        }
        meta.component = instance;
        meta.initialized = true;
        meta.initializing = false;
        meta.initialization = null;
    });
};

const markRegistryInitializing = (registry: ComponentRegistry, descriptor: ComponentDescriptor, instance: ComponentInstance): void => {
    ensureRegistryMetadata(registry, descriptor, instance);
    const components = registry.components;
    descriptor.registryNames.forEach((name) => {
        const normalizedName = assertNonEmptyString(name, 'Registry name');
        const meta = components.get(normalizedName);
        if (!meta) {
            throw new Error(`Component registry missing metadata for ${normalizedName}`);
        }
        meta.component = instance;
        meta.initialized = false;
        meta.initializing = true;
        meta.initialization = null;
    });
};

const markRegistryReset = (registry: ComponentRegistry, descriptor: ComponentDescriptor, instance: ComponentInstance): void => {
    ensureRegistryMetadata(registry, descriptor, instance);
    const components = registry.components;
    descriptor.registryNames.forEach((name) => {
        const normalizedName = assertNonEmptyString(name, 'Registry name');
        const meta = components.get(normalizedName);
        if (!meta) {
            throw new Error(`Component registry missing metadata for ${normalizedName}`);
        }
        meta.component = instance;
        meta.initialized = false;
        meta.initializing = false;
        meta.initialization = null;
    });
};

const resolveLayoutShellComponent = (descriptor: ComponentDescriptor, mainStatusMonitor: ComponentInstance, componentLookup: Map<string, ComponentInstance>): ComponentInstance => {
    if (descriptor.key === 'mainStatusMonitor') {
        return mainStatusMonitor;
    }
    const identifier = descriptor.identifier;
    if (!identifier) {
        throw new Error(`Layout shell component ${descriptor.key} is missing an identifier`);
    }
    if (componentLookup.has(identifier)) {
        const candidate = componentLookup.get(identifier);
        if (candidate) {
            return candidate;
        }
        throw new Error(`Layout shell component ${descriptor.key} is missing`);
    }
    throw new Error(`Layout shell component ${descriptor.key} is unavailable`);
};

export { ensureRegistryMetadata, markRegistryInitialized, markRegistryInitializing, markRegistryReset, resolveLayoutShellComponent };
