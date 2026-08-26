/* SoAI - Shared errors lifecycle cancellation [frontend/assets/ts/core/errors/lifecycleCancellation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

class LifecycleCancellationError extends Error {
    readonly reason: string;

    constructor(message: string, reason: string) {
        super(message);
        this.name = 'LifecycleCancellationError';
        this.reason = reason;
    }
}

type ErrorNameCandidate = {
    readonly name?: string;
};

const isErrorNameCandidate = <T>(value: T): value is T & ErrorNameCandidate => typeof value === 'object' && value !== null;

const isLifecycleCancellationError = <T>(value: T): boolean => {
    if (value instanceof LifecycleCancellationError) {
        return true;
    }
    if (!isErrorNameCandidate(value)) {
        return false;
    }
    return value.name === 'LifecycleCancellationError';
};

export { LifecycleCancellationError, isLifecycleCancellationError };
