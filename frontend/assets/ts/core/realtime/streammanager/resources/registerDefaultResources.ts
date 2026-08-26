/* SoAI - Shared realtime register default resources [frontend/assets/ts/core/realtime/streammanager/resources/registerDefaultResources.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { DEFAULT_RESOURCE_FACTORIES } from '@core/realtime/streammanager/resources/defaultFactories.ts';
import { AUTO_START, DETACHED_AUTO_START, PRIORITIZED } from '@core/realtime/streammanager/resources/ids.ts';
import type { ResourceFactory, ResourceFactoryManager } from '@core/realtime/streammanager/types.ts';
import { windowIdentity } from '@core/runtime/windowIdentity.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';

const registerDefaultResources = (manager: ResourceFactoryManager): void => {
    if (!isObject(manager)) {
        throw new Error('registerDefaultResources requires manager');
    }
    if (!isFunction(manager.registerResource)) {
        throw new Error('registerDefaultResources requires registerResource');
    }

    const prioritized = new Set(PRIORITIZED);
    const autoStartSet = windowIdentity.isDetachedContext() ? DETACHED_AUTO_START : AUTO_START;

    const registerOne = (name: string): void => {
        const factory: ResourceFactory | undefined = DEFAULT_RESOURCE_FACTORIES[name];
        if (!factory) {
            throw new Error(`Missing default resource factory for ${name}`);
        }
        const config = factory(manager);
        manager.registerResource(name, { ...config, autoStart: autoStartSet.has(name) });
    };

    prioritized.forEach((name) => {
        if (name) {
            registerOne(name);
        }
    });

    for (const name of Object.keys(DEFAULT_RESOURCE_FACTORIES)) {
        if (prioritized.has(name)) continue;
        registerOne(name);
    }
};

export { registerDefaultResources };
