/* SoAI - Shared API request runtime [frontend/assets/ts/core/api/requestRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { handleAuthenticationFailure } from '@core/api/actions.ts';
import { NETWORK_FAILURE_THRESHOLD } from '@core/api/constants.ts';
import { getAuthManager } from '@core/auth/runtime.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { log } from '@core/api/serviceSupport.ts';
import type { APIErrorMetadataValue } from '@core/apiError.ts';

interface ApiRequestRuntimeDependencies {
    getBaseUrl: () => string | null;
    recoverFromNetworkFailure: (baseUrl: string) => void;
}

class ApiRequestRuntime {
    readonly #dependencies: ApiRequestRuntimeDependencies;
    #networkErrorBase: string | null = null;
    #networkErrorCount = 0;

    constructor(dependencies: ApiRequestRuntimeDependencies) {
        this.#dependencies = dependencies;
    }

    resetNetworkErrorState = (): void => {
        this.#networkErrorBase = null;
        this.#networkErrorCount = 0;
    };

    registerNetworkError = (): void => {
        const currentBaseUrl = this.#dependencies.getBaseUrl();
        if (!currentBaseUrl) return;
        if (this.#networkErrorBase !== currentBaseUrl) {
            this.#networkErrorBase = currentBaseUrl;
            this.#networkErrorCount = 0;
        }
        this.#networkErrorCount += 1;
        if (this.#networkErrorCount < NETWORK_FAILURE_THRESHOLD) return;
        this.resetNetworkErrorState();
        this.#dependencies.recoverFromNetworkFailure(currentBaseUrl);
    };

    handleAuthenticationError = (error: APIErrorMetadataValue, targetEndpoint: string): Promise<void> => {
        return handleAuthenticationFailure(error, targetEndpoint, {
            waitForAuthService: async () => getAuthManager(),
            logWarning: (message, logoutError) => {
                log('warn', message, ensureError(logoutError));
            }
        });
    };
}

export { ApiRequestRuntime };
