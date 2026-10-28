/* SoAI - RAG ingestion terminal status resolution [frontend/assets/ts/features/chat/ragingestion/finalization/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RagIngestionStatus } from '@features/chat/ingestion/types.ts';

const isRagIngestionTerminal = (status: RagIngestionStatus): boolean => status.state === 'cancelled' || status.state === 'submitted' || status.state === 'failed';

const resolveCompletedRagIngestionStatus = (inputArguments: { status: RagIngestionStatus | null; queuedCount: number; inFlightCount: number }): RagIngestionStatus | null => {
    const current = inputArguments.status;
    if (!current) {
        return null;
    }
    if (isRagIngestionTerminal(current)) {
        return null;
    }
    if (inputArguments.queuedCount > 0 || inputArguments.inFlightCount > 0) {
        return null;
    }
    return { ...current, state: current.succeeded > 0 ? 'submitted' : 'failed', queued: 0, inFlight: 0 };
};

export { isRagIngestionTerminal, resolveCompletedRagIngestionStatus };
