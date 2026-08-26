/* SoAI - Transport-aware WebUI auth transition owner [frontend/assets/ts/core/auth/transitionOwner.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getGlobalScope } from '@core/environment/public.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { isFunction } from '@core/typeGuards.ts';

const AUTH_COOKIE_LOCK_NAME = 'soai.webui.auth-cookie-transition.v1';

class AuthTransitionUnavailableError extends Error {}

class AuthTransitionOwner {
    #queueTail: Promise<void> = Promise.resolve();
    #generation = 0;

    async runCookieMutation<TResult>(operation: () => Promise<TResult>): Promise<TResult> {
        const generation = this.#generation;
        const globalScope = getGlobalScope();
        const lockManager = globalScope.navigator?.locks;
        if (lockManager && isFunction(lockManager.request)) {
            return await lockManager.request(AUTH_COOKIE_LOCK_NAME, { mode: 'exclusive' }, async (): Promise<TResult> => await this.#runQueued(operation, generation));
        }
        if (globalScope.isSecureContext === true) {
            throw new AuthTransitionUnavailableError('Web Locks API is required for secure authentication changes.');
        }
        return await this.#runQueued(operation, generation);
    }

    async #runQueued<TResult>(operation: () => Promise<TResult>, generation: number): Promise<TResult> {
        const previous = this.#queueTail;
        const queueGate = createDeferred<void>();
        this.#queueTail = previous.then(() => queueGate.promise);
        await previous;
        try {
            if (generation !== this.#generation) {
                throw new DOMException('Authentication transition was cancelled.', 'AbortError');
            }
            return await operation();
        } finally {
            queueGate.resolve();
        }
    }

    async waitForCookieTransition(): Promise<void> {
        await this.runCookieMutation(async (): Promise<void> => undefined);
    }

    reset(): void {
        this.#generation += 1;
    }
}

export { AUTH_COOKIE_LOCK_NAME, AuthTransitionOwner, AuthTransitionUnavailableError };
