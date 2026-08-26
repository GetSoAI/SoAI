/* SoAI - Chat feature RAG ingestion batch results [frontend/assets/ts/features/chat/ragingestion/ragIngestionBatchResults.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { KnowledgeAttachmentSummary } from '@core/api/contracts/webuiAttachmentContracts.ts';
import type { RagBatchResultResponse, RagBatchUploadResponse } from '@core/api/contracts/webuiRagContracts.ts';

type RagBatchUploadOutcome = {
    succeededCount: number;
    failedCount: number;
    rateLimitedCount: number;
    maxRetryAfterSeconds: number;
    rateLimitedFiles: File[];
    knowledgeAttachment: KnowledgeAttachmentSummary | null;
};

const resolveBatchResultFileByIndex = (files: readonly File[], item: RagBatchResultResponse): File => {
    const itemIndex = item.index;
    const file = files[itemIndex];
    if (!file || itemIndex < 0) {
        throw new Error('Batch upload result index is out of range');
    }
    return file;
};

const parseRagBatchUploadOutcome = (payload: RagBatchUploadResponse, files: readonly File[]): RagBatchUploadOutcome => {
    const results = payload.results;
    if (!results) {
        throw new Error('Batch upload response is missing results');
    }

    let succeededCount = 0;
    let failedCount = 0;
    let rateLimitedCount = 0;
    let maxRetryAfterSeconds = 0;
    const rateLimitedFiles: File[] = [];
    const knowledgeAttachment = payload.knowledgeAttachment ?? null;

    for (const item of results) {
        const entryStatus = item.status;
        const file = resolveBatchResultFileByIndex(files, item);
        if (entryStatus === 'queued') {
            succeededCount += 1;
            continue;
        }
        if (entryStatus === 'rate_limited') {
            rateLimitedCount += 1;
            const retryAfterSeconds = item.retryAfterSeconds === undefined ? 0 : Math.max(0, Math.trunc(item.retryAfterSeconds));
            maxRetryAfterSeconds = Math.max(maxRetryAfterSeconds, retryAfterSeconds);
            rateLimitedFiles.push(file);
            continue;
        }
        failedCount += 1;
    }

    return {
        succeededCount,
        failedCount,
        rateLimitedCount,
        maxRetryAfterSeconds,
        rateLimitedFiles,
        knowledgeAttachment
    };
};

export { parseRagBatchUploadOutcome };
export type { RagBatchUploadOutcome };
