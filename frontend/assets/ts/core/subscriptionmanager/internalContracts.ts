/* SoAI - Shared subscription manager internal contracts [frontend/assets/ts/core/subscriptionmanager/internalContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasFunctionProperties, isObject } from '@core/typeGuards.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { type StreamManagerInterface } from '@core/subscriptionmanager/contracts.ts';

const REQUIRED_RESOURCE_METHODS: readonly string[] = Object.freeze(['ensureReady', 'ensureResourceStarted', 'getResource']);
const REQUIRED_SUBSCRIPTION_METHODS: readonly string[] = Object.freeze(['subscribeResourceState', 'subscribeResourceValue', 'unsubscribe']);

const isStreamManagerInterface = <T>(candidate: T): candidate is T & StreamManagerInterface => {
    if (candidate === null || candidate === undefined) {
        return false;
    }
    if (!isObject(candidate)) return false;
    if (!('resources' in candidate) || !('subscriptions' in candidate)) return false;
    const resources = candidate.resources;
    const subscriptions = candidate.subscriptions;
    return isObject(resources) && hasFunctionProperties(resources, REQUIRED_RESOURCE_METHODS) && isObject(subscriptions) && hasFunctionProperties(subscriptions, REQUIRED_SUBSCRIPTION_METHODS);
};

const validateStreamManager = <T>(candidate: T): T & StreamManagerInterface => {
    if (!isStreamManagerInterface(candidate)) {
        throw new Error('Stream manager module not initialized');
    }
    return candidate;
};

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

const log = (level: LogLevel, ownerId: string, message: string, error?: Error): void => {
    const reporter = errorHandler[level];
    if (typeof reporter === 'function') {
        errorHandler[level](ownerId, message, error);
    }
};

export { isStreamManagerInterface, validateStreamManager };
export type { LogLevel };
export { log };
