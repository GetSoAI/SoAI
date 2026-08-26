/* SoAI - Shared auth runtime [frontend/assets/ts/core/auth/runtime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SessionInvalidationResult } from '@core/auth/types.ts';
import { resolveOptionalKernelService, resolveKernelService } from '@core/runtime/runtimeContext.ts';

interface AuthManagerRuntime {
    isAuthenticated: boolean;
    invalidateSession: () => Promise<SessionInvalidationResult>;
    recoverRotatedSession: () => Promise<void>;
}

type AuthManagerRuntimeCandidate = {
    readonly isAuthenticated?: boolean;
    readonly invalidateSession?: () => Promise<SessionInvalidationResult>;
    readonly recoverRotatedSession?: () => Promise<void>;
};

const isAuthManagerRuntimeCandidate = <T>(value: T): value is T & AuthManagerRuntimeCandidate => typeof value === 'object' && value !== null;

const isAuthManagerRuntime = <T>(value: T): value is T & AuthManagerRuntime => {
    if (!isAuthManagerRuntimeCandidate(value)) {
        return false;
    }
    const invalidateSessionValue = value.invalidateSession;
    return typeof value.isAuthenticated === 'boolean' && typeof invalidateSessionValue === 'function' && typeof value.recoverRotatedSession === 'function';
};

const requireAuthManager = (): AuthManagerRuntime => {
    const candidate = resolveKernelService('core.auth');
    if (!isAuthManagerRuntime(candidate)) throw new Error('core.auth is not configured');
    return candidate;
};

const getAuthManager = (): AuthManagerRuntime | null => {
    const candidate = resolveOptionalKernelService('core.auth');
    return isAuthManagerRuntime(candidate) ? candidate : null;
};

export { getAuthManager, requireAuthManager };
export type { AuthManagerRuntime };
