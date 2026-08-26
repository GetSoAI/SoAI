/* SoAI - Shared connection state listeners [frontend/assets/ts/core/connectionstate/listeners.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { isFunction, isNullOrUndefined } from '@core/typeGuards.ts';
import type { BaseUrlListener, OnChangeOptions } from '@core/connectionstate/contracts.ts';
import type { ConnectionStateState } from '@core/connectionstate/state.ts';

const subscribeBaseUrlChange = (state: ConnectionStateState, listener: BaseUrlListener, options: OnChangeOptions, warn: (message: string, error: Error) => void): (() => void) => {
    if (!isFunction(listener)) {
        return () => {};
    }

    const { immediate = true } = options;
    state.listeners.add(listener);

    if (immediate) {
        try {
            listener(state.baseUrl);
        } catch (error) {
            warn('Immediate listener execution failed', ensureError(error));
        }
    }

    return () => {
        state.listeners.delete(listener);
    };
};

const subscribeBaseUrlOnce = (state: ConnectionStateState, listener: BaseUrlListener, options: OnChangeOptions, warn: (message: string, error: Error) => void): (() => void) => {
    if (!isFunction(listener)) {
        return () => {};
    }

    let unsubscribeRef: (() => void) | null = null;
    let pendingUnsubscribe = false;
    let delivered = false;

    const wrappedListener = (value: string | null): void => {
        if (isNullOrUndefined(value)) {
            return;
        }
        if (delivered) {
            return;
        }
        delivered = true;
        if (unsubscribeRef) {
            unsubscribeRef();
        } else {
            pendingUnsubscribe = true;
        }
        try {
            listener(value);
        } catch (error) {
            warn('One-time listener failed', ensureError(error));
        }
    };

    unsubscribeRef = subscribeBaseUrlChange(state, wrappedListener, options, warn);
    if (pendingUnsubscribe) {
        unsubscribeRef();
    }

    return (): void => {
        unsubscribeRef?.();
    };
};

export { subscribeBaseUrlChange, subscribeBaseUrlOnce };
