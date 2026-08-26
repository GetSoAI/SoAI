/* SoAI - Shared frontend routing router boundary contracts [frontend/assets/ts/core/routing/router/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RouterDependencies } from '@core/routing/router/routerDependencies.ts';
import { isFunction, isMap, isObject } from '@core/typeGuards.ts';

const assertRouterDependencies = (dependencies: RouterDependencies): void => {
    const { dom, storage, auth, api, streamManager, state, cleanupManager, errorHandler, componentRegistry, pageRegistry, getSidebarService } = dependencies;

    if (!isObject(errorHandler)) {
        throw new Error('Error handler must be ready before router');
    }
    if (!isObject(dom)) {
        throw new Error('DOM service must be ready before router');
    }
    if (!isFunction(dom.getBody)) {
        throw new Error('DOM service must expose getBody');
    }
    if (!isFunction(dom.getDocument)) {
        throw new Error('DOM service must expose getDocument');
    }
    if (!isObject(storage)) {
        throw new Error('Storage service must be ready before router');
    }
    if (!isObject(auth)) {
        throw new Error('Auth service must be ready before router');
    }
    if (!isObject(api)) {
        throw new Error('API service must be ready before router');
    }
    if (!isObject(streamManager)) {
        throw new Error('Stream manager must be ready before router');
    }
    if (!isFunction(streamManager.ensureReady)) {
        throw new Error('Router requires streamManager.ensureReady');
    }
    if (!isFunction(streamManager.ensureResourceStarted)) {
        throw new Error('Router requires streamManager.ensureResourceStarted');
    }
    if (!isObject(state)) {
        throw new Error('State service must be ready before router');
    }
    if (!isObject(state.section)) {
        throw new Error('State section tracker must be ready before router');
    }
    if (!isFunction(state.section.cleanup)) {
        throw new Error('Router requires sectionTracker.cleanup');
    }
    if (!isFunction(state.section.initialize)) {
        throw new Error('Router requires sectionTracker.initialize');
    }
    if (!isFunction(state.setTabState)) {
        throw new Error('Router requires stateManager.setTabState');
    }
    if (!isObject(cleanupManager)) {
        throw new Error('Cleanup manager must be ready before router');
    }
    if (!isFunction(cleanupManager.cleanupAll)) {
        throw new Error('Router requires cleanupManager.cleanupAll');
    }
    if (!isMap(componentRegistry)) {
        throw new TypeError('Router requires a componentRegistry map');
    }
    if (!isObject(pageRegistry)) {
        throw new TypeError('Router requires a pageRegistry');
    }
    if (!isFunction(pageRegistry.create) || !isFunction(pageRegistry.getMeta)) {
        throw new TypeError('Router requires a valid pageRegistry contract');
    }
    if (!isFunction(getSidebarService)) {
        throw new Error('Router requires getSidebarService to be callable');
    }
};

export { assertRouterDependencies };
