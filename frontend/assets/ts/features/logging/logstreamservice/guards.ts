/* SoAI - Logging feature log stream service guards [frontend/assets/ts/features/logging/logstreamservice/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasFunctionProperties, isObject } from '@core/typeGuards.ts';
import type { StreamManagerWithLogs } from '@features/logging/logstreamservice/types.ts';

const isLogStreamManager = <T>(candidate: T): candidate is T & StreamManagerWithLogs => {
    if (!isObject(candidate)) {
        return false;
    }
    if (!('resources' in candidate) || !('subscriptions' in candidate) || !('connection' in candidate)) return false;
    const resources = candidate.resources;
    const subscriptions = candidate.subscriptions;
    const connection = candidate.connection;
    return isObject(resources) && hasFunctionProperties(resources, ['ensureReady']) && isObject(subscriptions) && hasFunctionProperties(subscriptions, ['subscribeBundle', 'unsubscribe']) && isObject(connection) && hasFunctionProperties(connection, ['streamLogs']);
};

export { isLogStreamManager };
