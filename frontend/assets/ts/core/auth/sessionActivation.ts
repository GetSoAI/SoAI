/* SoAI - Shared auth session activation [frontend/assets/ts/core/auth/sessionActivation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';

interface AuthLoginSource {
    isAuthenticated: boolean;
    onLogin: (callback: () => void) => (() => void) | void;
}

interface DeferredSessionActivationOptions {
    auth: AuthLoginSource;
    getCurrentListener: () => (() => void) | null;
    setCurrentListener: (listener: (() => void) | null) => void;
    activate: () => Promise<void>;
    onActivationError: (error: Error) => void;
    onCleanupError: (error: Error) => void;
}

const clearDeferredSessionActivation = ({ getCurrentListener, setCurrentListener, onCleanupError }: Pick<DeferredSessionActivationOptions, 'getCurrentListener' | 'setCurrentListener' | 'onCleanupError'>): void => {
    const currentListener = getCurrentListener();
    if (!currentListener) {
        return;
    }
    try {
        currentListener();
    } catch (error) {
        onCleanupError(ensureError(error));
    } finally {
        setCurrentListener(null);
    }
};

const ensureDeferredSessionActivation = ({ auth, getCurrentListener, setCurrentListener, activate, onActivationError, onCleanupError }: DeferredSessionActivationOptions): boolean => {
    const currentListener = getCurrentListener();
    if (auth.isAuthenticated || currentListener) {
        return false;
    }
    const unsubscribe = auth.onLogin(() => {
        clearDeferredSessionActivation({
            getCurrentListener,
            setCurrentListener,
            onCleanupError
        });
        void activate().catch((error) => {
            onActivationError(ensureError(error));
        });
    });
    setCurrentListener(typeof unsubscribe === 'function' ? unsubscribe : null);
    return true;
};

export { clearDeferredSessionActivation, ensureDeferredSessionActivation };
