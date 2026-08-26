/* SoAI - Shared API probe fetch [frontend/assets/ts/core/api/probeFetch.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';

interface ProbeFetchOptions {
    signal: AbortSignal;
    acceptJson?: boolean;
    credentials?: RequestCredentials;
}

const probeFetch = async (url: string, options: ProbeFetchOptions): Promise<Response> => {
    const { signal, acceptJson = false, credentials = 'omit' } = options;
    const requestConfiguration: RequestInit = {
        method: 'GET',
        signal,
        credentials,
        cache: 'no-store'
    };
    if (acceptJson) {
        requestConfiguration.headers = { Accept: 'application/json' };
    }
    try {
        return await fetch(url, requestConfiguration);
    } catch (error) {
        throw ensureError(error);
    }
};

export { probeFetch };
export type { ProbeFetchOptions };
