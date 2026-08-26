/* SoAI - RAG ingestion cancellation service [frontend/assets/ts/features/chat/ragingestion/cancellation/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { KnowledgeAttachmentSummary } from '@core/api/contracts/webuiAttachmentContracts.ts';
import type { RequestOptions } from '@core/api/types/request.ts';
import type { RagIngestionStatus } from '@features/chat/public.ts';
import { resolveCancelledIngestionStatus, resolveKnowledgeAttachmentIdForCancellation } from '@features/chat/ragingestion/cancellation/state.ts';

type RagIngestionCancellationFlowArguments = {
    status: RagIngestionStatus | null;
    conversationId: string;
    inFlight: number;
    applyCancelledStatus: (status: RagIngestionStatus) => void;
    getCurrentStatus: () => RagIngestionStatus | null;
    isDisposed: () => boolean;
    cancelKnowledgeAttachment: (conversationId: string, knowledgeAttachmentId: string, options?: RequestOptions) => Promise<KnowledgeAttachmentSummary>;
    signal: AbortSignal | null;
};

const cancelRagIngestionFlow = async (inputArguments: RagIngestionCancellationFlowArguments): Promise<void> => {
    const knowledgeAttachmentId = inputArguments.status ? resolveKnowledgeAttachmentIdForCancellation(inputArguments.status) : null;
    const cancelledStatus = resolveCancelledIngestionStatus(inputArguments.status, inputArguments.conversationId, inputArguments.inFlight);
    if (cancelledStatus === null) {
        return;
    }
    inputArguments.applyCancelledStatus(cancelledStatus);
    if (knowledgeAttachmentId === null) {
        return;
    }
    const summary = await inputArguments.cancelKnowledgeAttachment(cancelledStatus.conversationId, knowledgeAttachmentId, { signal: inputArguments.signal ?? undefined });
    const currentStatus = inputArguments.getCurrentStatus();
    if (inputArguments.isDisposed() || currentStatus === null || currentStatus.conversationId !== cancelledStatus.conversationId || currentStatus.state !== 'cancelled') {
        return;
    }
    inputArguments.applyCancelledStatus({ ...currentStatus, knowledgeAttachment: summary });
};

export { cancelRagIngestionFlow };
export type { RagIngestionCancellationFlowArguments };
