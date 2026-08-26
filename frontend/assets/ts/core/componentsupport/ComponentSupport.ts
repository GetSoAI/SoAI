/* SoAI - Frontend component support ownership [frontend/assets/ts/core/componentsupport/ComponentSupport.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ComponentRegistry } from '@core/componentsupport/registry.ts';
import { configureCollection } from '@core/componentsupport/collection.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { resolveKernelService } from '@core/runtime/runtimeContext.ts';

const COMPONENT_REGISTRY_SERVICE_ID = 'core.componentRegistry';
const COMPONENT_SUPPORT_SERVICE_ID = 'core.componentSupport';

class ComponentSupport {
    ComponentRegistry: typeof ComponentRegistry;
    componentRegistry: ComponentRegistry;
    collectionSupport: { configure: typeof configureCollection };

    constructor(componentRegistry: ComponentRegistry) {
        this.ComponentRegistry = ComponentRegistry;
        this.componentRegistry = componentRegistry;
        this.collectionSupport = { configure: configureCollection };
    }
}

const isComponentRegistry = (value: ComponentRegistry | JsonValue | null | undefined): value is ComponentRegistry => {
    return value instanceof ComponentRegistry;
};

const getComponentRegistry = (): ComponentRegistry => {
    const candidate = resolveKernelService(COMPONENT_REGISTRY_SERVICE_ID);
    if (!isComponentRegistry(candidate)) {
        throw new Error(`${COMPONENT_REGISTRY_SERVICE_ID} is not registered`);
    }
    return candidate;
};

const isComponentSupport = (value: ComponentSupport | JsonValue | null | undefined): value is ComponentSupport => {
    return value instanceof ComponentSupport;
};

const getComponentSupport = (): ComponentSupport => {
    const candidate = resolveKernelService(COMPONENT_SUPPORT_SERVICE_ID);
    if (!isComponentSupport(candidate)) {
        throw new Error(`${COMPONENT_SUPPORT_SERVICE_ID} is not registered`);
    }
    return candidate;
};

export { ComponentSupport, ComponentRegistry, getComponentRegistry, getComponentSupport, configureCollection, COMPONENT_REGISTRY_SERVICE_ID, COMPONENT_SUPPORT_SERVICE_ID };
