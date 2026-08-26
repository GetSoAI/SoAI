/* SoAI - Shared main status monitor validation [frontend/assets/ts/core/mainstatusmonitor/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasFunctionProperties, isBoolean, isFunction, isObject } from '@core/typeGuards.ts';
import type { AuthManagerInterface, StreamManagerInterface } from '@core/mainstatusmonitor/types.ts';

const isAuthManager = <T>(value: T): value is T & AuthManagerInterface => {
    return isObject(value) && 'onLogin' in value && isFunction(value.onLogin) && 'isAuthenticated' in value && isBoolean(value.isAuthenticated);
};

const isStreamManager = <T>(value: T): value is T & StreamManagerInterface => {
    if (!isObject(value)) {
        return false;
    }
    if (!('resources' in value) || !('subscriptions' in value)) return false;
    const resources = value.resources;
    const subscriptions = value.subscriptions;
    return isObject(resources) && hasFunctionProperties(resources, ['ensureReady', 'getResource', 'ensureResourceStarted']) && isObject(subscriptions) && hasFunctionProperties(subscriptions, ['subscribeResourceState']);
};

export { isAuthManager, isStreamManager };
