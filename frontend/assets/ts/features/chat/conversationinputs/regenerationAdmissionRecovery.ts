/* SoAI - Ambiguous conversation input admission recovery [frontend/assets/ts/features/chat/conversationinputs/regenerationAdmissionRecovery.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNetworkError, isRequestTimeoutError } from '@core/apiError.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError, isErrorHttpStatus } from '@core/errors/coerce.ts';
import { sleepMsAbortable } from '@core/primitives/sleepMsAbortable.ts';

const RECOVERY_DELAYS_MS: readonly number[] = [0, 250, 1000, 3000];

interface AmbiguousAdmissionRecoveryRequest<TReceipt> {
    admit: () => Promise<TReceipt>;
    readReceipt: () => Promise<TReceipt>;
    signal: AbortSignal;
}

const isAmbiguousAdmissionError = (error: Error): boolean => isNetworkError(error) || isRequestTimeoutError(error);

const recoverAmbiguousRegenerationAdmission = async <TReceipt>(request: AmbiguousAdmissionRecoveryRequest<TReceipt>): Promise<TReceipt> => {
    let admissionError: Error;
    try {
        return await request.admit();
    } catch (error) {
        admissionError = ensureError(error);
        if (!isAmbiguousAdmissionError(admissionError)) throw admissionError;
    }
    for (const delayMs of RECOVERY_DELAYS_MS) {
        if (delayMs > 0) await sleepMsAbortable(request.signal, delayMs);
        try {
            return await request.readReceipt();
        } catch (error) {
            const runtimeError = ensureError(error);
            if (isAbortError(runtimeError)) throw runtimeError;
            if (!isErrorHttpStatus(runtimeError, 404) && !isAmbiguousAdmissionError(runtimeError)) throw runtimeError;
        }
    }
    throw admissionError;
};

export { recoverAmbiguousRegenerationAdmission };
