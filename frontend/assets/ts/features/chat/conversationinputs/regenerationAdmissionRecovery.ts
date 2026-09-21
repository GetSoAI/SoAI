/* SoAI - Ambiguous conversation regeneration admission recovery [frontend/assets/ts/features/chat/conversationinputs/regenerationAdmissionRecovery.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationRegenerationReceipt } from '@core/api/contracts/webuiMessageRegenerationContracts.ts';
import { isNetworkError, isRequestTimeoutError } from '@core/apiError.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError, isErrorHttpStatus } from '@core/errors/coerce.ts';
import { sleepMsAbortable } from '@core/primitives/sleepMsAbortable.ts';

const RECOVERY_DELAYS_MS: readonly number[] = [0, 250, 1000, 3000];

interface RegenerationAdmissionRecoveryRequest {
    conversationId: string;
    clientId: string;
    clientRequestId: string;
    admissionError: Error;
    signal: AbortSignal;
    readStatus: (conversationId: string, clientId: string, clientRequestId: string) => Promise<ConversationRegenerationReceipt>;
}

const recoverAmbiguousRegenerationAdmission = async (request: RegenerationAdmissionRecoveryRequest): Promise<ConversationRegenerationReceipt> => {
    for (const delayMs of RECOVERY_DELAYS_MS) {
        if (delayMs > 0) await sleepMsAbortable(request.signal, delayMs);
        try {
            return await request.readStatus(request.conversationId, request.clientId, request.clientRequestId);
        } catch (error) {
            const runtimeError = ensureError(error);
            if (isAbortError(runtimeError)) throw runtimeError;
            if (!isErrorHttpStatus(runtimeError, 404) && !isNetworkError(runtimeError) && !isRequestTimeoutError(runtimeError)) throw runtimeError;
        }
    }
    throw request.admissionError;
};

export { recoverAmbiguousRegenerationAdmission };
