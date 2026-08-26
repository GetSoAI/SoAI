/* SoAI - Shared API head fetch [frontend/assets/ts/core/api/headFetch.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';

interface HeadFetchOptions {
    signal: AbortSignal;
    credentials?: RequestCredentials;
}

const headFetch = async (url: string, options: HeadFetchOptions): Promise<Response> => {
    const { signal, credentials = 'same-origin' } = options;
    const requestConfiguration: RequestInit = {
        method: 'HEAD',
        signal,
        credentials,
        cache: 'no-store'
    };
    try {
        return await fetch(url, requestConfiguration);
    } catch (error) {
        throw ensureError(error);
    }
};

export { headFetch };
export type { HeadFetchOptions };
