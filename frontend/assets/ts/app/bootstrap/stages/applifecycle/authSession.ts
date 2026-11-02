/* SoAI - Application authentication intent and subscription lifetime [frontend/assets/ts/app/bootstrap/stages/applifecycle/authSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { LifecycleAuthHandlerHost, LifecycleAuthSubscriptions } from '@app/bootstrap/stages/applifecycle/contracts.ts';
import type { AuthEpochIntentCallback } from '@core/auth/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { runCleanup } from '@core/lifecycle/cleanup.ts';

interface AuthLifecycleEvents {
    readonly authEpoch: number;
    readonly isAuthenticated: boolean;
    onEpochIntent: (callback: AuthEpochIntentCallback) => () => void;
    onLogin: (callback: () => void | Promise<void>) => (() => void) | void;
    onLogout: (callback: () => void | Promise<void>) => (() => void) | void;
}

interface RegisterLifecycleAuthHandlersOptions {
    auth: AuthLifecycleEvents;
    host: LifecycleAuthHandlerHost;
}

const registerLifecycleAuthHandlers = ({ auth, host }: RegisterLifecycleAuthHandlersOptions): LifecycleAuthSubscriptions => {
    let transitionTail: Promise<void> = Promise.resolve();
    let deferredLoginEpoch: number | null = null;
    let activatedEpoch: number | null = null;
    let initializingEpoch: number | null = null;
    const enqueueTransition = (transition: () => Promise<void>, label: string): void => {
        const task = transitionTail.then(transition, transition);
        transitionTail = task;
        void task.catch((error) => errorHandler.error('AppLifecycle', `${label} handler failed`, ensureError(error)));
    };
    const enqueueLogin = (epoch: number): void =>
        enqueueTransition(async () => {
            if (auth.authEpoch !== epoch || !auth.isAuthenticated) return;
            if (activatedEpoch === epoch) {
                await host.refreshAccess();
                return;
            }
            initializingEpoch = epoch;
            try {
                await host.handleLogin();
            } finally {
                if (initializingEpoch === epoch) initializingEpoch = null;
            }
            if (auth.authEpoch === epoch && auth.isAuthenticated) activatedEpoch = epoch;
        }, 'Login');
    const unsubscribeEpochIntent = auth.onEpochIntent((intent) => {
        deferredLoginEpoch = null;
        host.invalidateSession(intent);
        if (intent.type === 'authenticated' && (activatedEpoch !== null || initializingEpoch !== null)) {
            activatedEpoch = null;
            enqueueTransition(host.retireSession, 'Session replacement');
        }
    });
    const unsubscribeLogin = auth.onLogin(() => {
        const epoch = auth.authEpoch;
        if (host.isBootstrapInProgress()) {
            deferredLoginEpoch = epoch;
            return;
        }
        enqueueLogin(epoch);
    });
    const unsubscribeLogout = auth.onLogout(() => enqueueTransition(host.handleLogout, 'Logout'));
    return {
        unsubscribeLogin: typeof unsubscribeLogin === 'function' ? unsubscribeLogin : () => {},
        unsubscribeLogout: typeof unsubscribeLogout === 'function' ? unsubscribeLogout : () => {},
        unsubscribeEpochIntent,
        resumeDeferredLogin: (sessionNeedsHandoff): void => {
            const deferred = deferredLoginEpoch;
            deferredLoginEpoch = null;
            if (!sessionNeedsHandoff && auth.isAuthenticated) activatedEpoch = auth.authEpoch;
            if (deferred !== null && sessionNeedsHandoff && auth.authEpoch === deferred) enqueueLogin(deferred);
        }
    };
};

class LifecycleAuthSession {
    #subscriptions: LifecycleAuthSubscriptions | null = null;

    register(options: RegisterLifecycleAuthHandlersOptions): void {
        if (!this.#subscriptions) this.#subscriptions = registerLifecycleAuthHandlers(options);
    }

    resumeDeferredLogin(sessionNeedsHandoff: boolean): void {
        this.#subscriptions?.resumeDeferredLogin(sessionNeedsHandoff);
    }

    release(): void {
        const subscriptions = this.#subscriptions;
        this.#subscriptions = null;
        if (!subscriptions) return;
        for (const dispose of [subscriptions.unsubscribeLogin, subscriptions.unsubscribeLogout, subscriptions.unsubscribeEpochIntent]) {
            runCleanup(dispose, (error) => errorHandler.warn('AppLifecycle', 'Authentication subscription cleanup failed', error));
        }
    }
}

export { LifecycleAuthSession, registerLifecycleAuthHandlers };
export type { AuthLifecycleEvents, RegisterLifecycleAuthHandlersOptions };
