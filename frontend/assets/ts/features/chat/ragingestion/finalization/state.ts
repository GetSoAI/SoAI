/* SoAI - RAG ingestion terminal status resolution [frontend/assets/ts/features/chat/ragingestion/finalization/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RagIngestionStatus } from '@features/chat/public.ts';

const resolveCompletedRagIngestionStatus = (inputArguments: { status: RagIngestionStatus | null; queuedCount: number; inFlightCount: number }): RagIngestionStatus | null => {
    const current = inputArguments.status;
    if (!current) {
        return null;
    }
    if (current.state === 'cancelled' || current.state === 'submitted') {
        return null;
    }
    if (inputArguments.queuedCount > 0 || inputArguments.inFlightCount > 0) {
        return null;
    }
    return { ...current, state: 'submitted', queued: 0, inFlight: 0 };
};

export { resolveCompletedRagIngestionStatus };
