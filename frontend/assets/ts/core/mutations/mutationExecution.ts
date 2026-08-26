/* SoAI - Durable mutation retry execution policy [frontend/assets/ts/core/mutations/mutationExecution.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError, isNetworkError } from '@core/apiError.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { createMutationRequestId, recoverMutationIdentityTimeSkew } from '@core/mutations/mutationIdentity.ts';

const executeMutationWithClockRecovery = async <T>(execute: (requestId: string) => Promise<T>): Promise<T> => {
    let requestId = createMutationRequestId();
    let recoveredClockSkew = false;
    let retriedAmbiguousTransport = false;
    while (true) {
        try {
            return await execute(requestId);
        } catch (error) {
            const runtimeError = ensureError(error);
            if (!recoveredClockSkew && recoverMutationIdentityTimeSkew(runtimeError)) {
                recoveredClockSkew = true;
                requestId = createMutationRequestId();
                continue;
            }
            const ambiguousAdmission = runtimeError instanceof APIError && runtimeError.code === 'database_timeout';
            if (!retriedAmbiguousTransport && (isNetworkError(runtimeError) || ambiguousAdmission)) {
                retriedAmbiguousTransport = true;
                continue;
            }
            throw runtimeError;
        }
    }
};

export { executeMutationWithClockRecovery };
