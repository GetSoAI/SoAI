/* SoAI - Bounded navigation redirect chains and preserved request metadata [frontend/assets/ts/core/routing/router/navigationRedirects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { NavigationOptions, NavigationRequest } from '@core/routing/router/types.ts';
import { filterStringArrayValue } from '@core/types/payloadArrayReaders.ts';
import { isObject } from '@core/typeGuards.ts';

const REDIRECT_CHAIN_META_KEY = '__soaiRedirectChain';
const MAX_REDIRECT_DEPTH = 8;

const createNavigationRedirectOptions = (request: NavigationRequest, currentPath: string, target: string, options: NavigationOptions): NavigationOptions => {
    const recorded = isObject(request.meta) ? request.meta[REDIRECT_CHAIN_META_KEY] : null;
    const redirectChain = [...filterStringArrayValue(recorded).filter(Boolean), currentPath];
    if (redirectChain.length > MAX_REDIRECT_DEPTH) throw new Error(`Router redirect depth exceeded ${MAX_REDIRECT_DEPTH}`);
    if (redirectChain.includes(target)) throw new Error(`Router detected redirect loop for route: ${target}`);
    const existingMeta = isObject(options.meta) ? options.meta : {};
    return { ...options, meta: { ...existingMeta, [REDIRECT_CHAIN_META_KEY]: redirectChain } };
};

export { createNavigationRedirectOptions, MAX_REDIRECT_DEPTH };
