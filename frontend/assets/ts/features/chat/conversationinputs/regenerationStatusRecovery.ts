/* SoAI - Latest conversation regeneration status recovery [frontend/assets/ts/features/chat/conversationinputs/regenerationStatusRecovery.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationLatestRegenerationStatus, ConversationRegenerationReceipt } from '@core/api/contracts/webuiMessageRegenerationContracts.ts';
import { ensureError } from '@core/errors/coerce.ts';

interface LatestRegenerationRecoveryRequest {
    conversationId: string;
    readStatus: (conversationId: string, signal: AbortSignal) => Promise<ConversationLatestRegenerationStatus>;
    applyReceipt: (conversationId: string, receipt: ConversationRegenerationReceipt) => void;
    signal: AbortSignal;
    logWarning: (message: string, error: Error) => void;
}

const recoverLatestConversationRegeneration = (request: LatestRegenerationRecoveryRequest): void => {
    if (request.signal.aborted) return;
    void request
        .readStatus(request.conversationId, request.signal)
        .then((status) => {
            if (!request.signal.aborted && status.status === 'attempt') request.applyReceipt(request.conversationId, status.attempt);
        })
        .catch((error) => {
            if (!request.signal.aborted) {
                request.logWarning('Failed to recover conversation regeneration', ensureError(error));
            }
        });
};

export { recoverLatestConversationRegeneration };
