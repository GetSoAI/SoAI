/* SoAI - Shared routing terminal access policy [frontend/assets/ts/core/routing/router/terminalAccessPolicy.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireStateManager } from '@core/state/runtime.ts';
import type { ApiService, AuthService } from '@core/routing/router/routerDependencies.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isFunction, isObject, isString } from '@core/typeGuards.ts';

interface TerminalAccessPolicyCache {
    decision: boolean | null;
    inFlight: Promise<boolean> | null;
    sessionKey: string | null;
    policyRevision: string | null;
}

const cache: TerminalAccessPolicyCache = {
    decision: null,
    inFlight: null,
    sessionKey: null,
    policyRevision: null
};

const TERMINAL_POLICY_CHANNEL_ID = 'soai.webui.terminal.policy';
const TERMINAL_POLICY_INVALIDATION_TYPE = 'terminal.policy.invalidate';

let terminalPolicySubscriptionBound = false;

const resolveSessionKey = (auth: AuthService): string => (auth.isAuthenticated === true ? 'authenticated' : 'anonymous');

const computeTerminalAccessDecision = async (auth: AuthService, api: ApiService): Promise<{ decision: boolean; policyRevision: string }> => {
    if (auth.isAuthenticated !== true) {
        return {
            decision: false,
            policyRevision: 'anonymous'
        };
    }
    if (!isObject(api.webui) || !isObject(api.webui.terminal) || !isFunction(api.webui.terminal.policy)) {
        throw new Error('API client must expose webui.terminal.policy');
    }
    const snapshot = await api.webui.terminal.policy();
    if (!isObject(snapshot)) {
        throw new Error('Terminal policy response must be an object');
    }
    const canAccessTerminal = snapshot.canAccessTerminal;
    const policyRevision = snapshot.policyRevision;
    if (typeof canAccessTerminal !== 'boolean') {
        throw new Error('Terminal policy response must include can_access_terminal');
    }
    if (!isString(policyRevision) || !policyRevision.trim()) {
        throw new Error('Terminal policy response must include policy_revision');
    }
    return {
        decision: canAccessTerminal,
        policyRevision: policyRevision.trim()
    };
};

const invalidateTerminalAccessPolicy = (): void => {
    cache.decision = null;
    cache.inFlight = null;
    cache.sessionKey = null;
    cache.policyRevision = null;
};

const publishTerminalAccessPolicyInvalidation = (): void => {
    invalidateTerminalAccessPolicy();
    requireStateManager().getCrossTabChannel(TERMINAL_POLICY_CHANNEL_ID).publish({ type: TERMINAL_POLICY_INVALIDATION_TYPE });
};

const bindTerminalAccessPolicyInvalidation = (): void => {
    if (terminalPolicySubscriptionBound) {
        return;
    }
    requireStateManager()
        .getCrossTabChannel(TERMINAL_POLICY_CHANNEL_ID)
        .subscribe((message: JsonValue | null | undefined) => {
            if (!isObject(message)) {
                return;
            }
            if (message['type'] !== TERMINAL_POLICY_INVALIDATION_TYPE) {
                return;
            }
            invalidateTerminalAccessPolicy();
        });
    terminalPolicySubscriptionBound = true;
};

const canAccessTerminal = async (auth: AuthService, api: ApiService): Promise<boolean> => {
    const sessionKey = resolveSessionKey(auth);
    if (cache.sessionKey !== sessionKey) {
        invalidateTerminalAccessPolicy();
        cache.sessionKey = sessionKey;
    }
    if (cache.decision !== null) {
        return cache.decision;
    }
    if (cache.inFlight) {
        return cache.inFlight;
    }
    cache.inFlight = computeTerminalAccessDecision(auth, api)
        .then((snapshot) => {
            if (cache.sessionKey === sessionKey) {
                cache.decision = snapshot.decision;
                cache.policyRevision = snapshot.policyRevision;
            }
            return snapshot.decision;
        })
        .finally(() => {
            if (cache.sessionKey === sessionKey) {
                cache.inFlight = null;
            }
        });
    return cache.inFlight;
};

export { bindTerminalAccessPolicyInvalidation, canAccessTerminal, invalidateTerminalAccessPolicy, publishTerminalAccessPolicyInvalidation };
