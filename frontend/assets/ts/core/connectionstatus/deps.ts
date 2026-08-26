/* SoAI - Shared connection status dependencies [frontend/assets/ts/core/connectionstatus/deps.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { getAuthManager } from '@core/auth/public.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { requirePerformanceNow } from '@core/environment/public.ts';
import { getStreamRuntime, type StreamRuntimeOwners } from '@core/realtime/streammanager/public.ts';
import { STATUS } from '@core/realtime/streammanager/resources/ids.ts';
import { isFunction, isNumber, isObject } from '@core/typeGuards.ts';

export type StreamManagerRef = StreamRuntimeOwners;

interface DiagnosticsManager {
    getDiagnostics?: () => { queueDepth?: number };
    getQueueDepth?: () => number;
}

export interface AuthManagerInterface {
    onLogin: (callback: () => void) => (() => void) | void;
    isAuthenticated: boolean;
}

type AuthManagerCandidate = AuthManagerInterface | JsonValue | null | undefined;
type StreamManagerCandidate = StreamManagerRef | JsonValue | null | undefined;

let statusStreamCache: string | null = null;
let diagnosticsManager: DiagnosticsManager | null = null;
let diagnosticsErrorLogged = false;

export const startTimer = (): number => requirePerformanceNow()();
export const readTimer = (token: number | null): number | null => (isNumber(token) ? Math.max(0, requirePerformanceNow()() - token) : null);

export const getStatusStream = (): string => {
    if (statusStreamCache === null) statusStreamCache = STATUS;
    return statusStreamCache;
};

export const requireAuthManager = (): AuthManagerInterface => {
    const authManager = getAuthManager();
    const isAuthManager = (value: AuthManagerCandidate): value is AuthManagerInterface => isObject(value) && 'onLogin' in value && isFunction(value.onLogin) && 'isAuthenticated' in value && typeof value.isAuthenticated === 'boolean';
    if (!isAuthManager(authManager)) {
        throw new Error('Auth manager is unavailable');
    }
    return authManager;
};

const hasRequiredManagerMethods = (candidate: StreamManagerCandidate): candidate is StreamManagerRef => {
    if (!isObject(candidate)) return false;
    return 'resources' in candidate && isObject(candidate.resources) && isFunction(candidate.resources.ensureReady) && isFunction(candidate.resources.ensureResourceStarted) && 'subscriptions' in candidate && isObject(candidate.subscriptions) && isFunction(candidate.subscriptions.subscribeResourceState);
};

export const resolveStreamManagerReference = (): StreamManagerRef | null => {
    const candidate = getStreamRuntime();
    return hasRequiredManagerMethods(candidate) ? candidate : null;
};

export const resetStreamManagerCaches = (): void => {
    diagnosticsManager = null;
    diagnosticsErrorLogged = false;
};

const resolveDiagnosticsManager = (): DiagnosticsManager | null => {
    if (diagnosticsManager && isFunction(diagnosticsManager.getDiagnostics)) return diagnosticsManager;
    const manager = resolveStreamManagerReference();
    if (manager && isFunction(manager.resources.getDiagnostics)) {
        diagnosticsManager = manager.resources;
        diagnosticsErrorLogged = false;
        return diagnosticsManager;
    }
    return null;
};

export const readQueueDepth = (): number | null => {
    const manager = resolveDiagnosticsManager();
    if (!manager) return null;

    try {
        if (isFunction(manager.getQueueDepth)) {
            const depth = manager.getQueueDepth();
            if (isNumber(depth) && Number.isFinite(depth)) return depth;
            if (depth === 0) return 0;
        }

        if (isFunction(manager.getDiagnostics)) {
            const diagnostics = manager.getDiagnostics();
            if (isObject(diagnostics)) {
                const depth = diagnostics['queueDepth'];
                if (isNumber(depth) && Number.isFinite(depth)) return depth;
                if (depth === 0) return 0;
            }
        }

        return null;
    } catch (error) {
        if (!diagnosticsErrorLogged) {
            diagnosticsErrorLogged = true;
            const runtimeError = ensureError(error);
            errorHandler.debug('ConnectionStatus', 'Diagnostics snapshot failed', runtimeError);
        }
        throw ensureError(error);
    }
};
