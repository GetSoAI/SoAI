/* SoAI - Frontend application page host [frontend/assets/ts/app/bootstrap/stages/pageHost.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PageHostInstance } from '@core/pageoutlet/types.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';

type PageHostApi = Pick<PageHostInstance, 'whenReady' | 'getCurrent'>;

const isPageHostApi = <T>(candidate: T): candidate is T & PageHostApi => {
    if (!isObject(candidate)) return false;
    return 'getCurrent' in candidate && isFunction(candidate.getCurrent) && 'whenReady' in candidate && isFunction(candidate.whenReady);
};

const requirePageHostApi = <T>(candidate: T, routeKey: string): T & PageHostApi => {
    if (!isObject(candidate)) {
        throw new Error(`Page outlet must provide an object host for route: ${routeKey}`);
    }
    if (!isPageHostApi(candidate)) {
        throw new Error(`Page host must expose a valid route lifecycle API for route: ${routeKey}`);
    }
    return candidate;
};

export { requirePageHostApi };
export type { PageHostApi };
