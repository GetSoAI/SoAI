/* SoAI - Chat feature queue service [frontend/assets/ts/features/chat/ragingestion/queue/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { sleepMs } from '@core/primitives/sleepMs.ts';
import type { RagDocumentsResponse } from '@core/api/contracts/webuiRagContracts.ts';
import { isNumber } from '@core/typeGuards.ts';

type RagDocumentListFetcher = (conversationId: string, options?: { limit?: number; offset?: number; includeDocuments?: boolean }) => Promise<RagDocumentsResponse>;

interface RagIngestionQueueLease {
    release: () => void;
}

const ACTIVE_DOCUMENT_STATUSES: readonly (keyof RagDocumentsResponse['statusCounts'])[] = ['queued', 'fetching', 'parsing', 'chunking', 'embedding'];
const DOCUMENT_FETCH_LIMIT = 500;
const MAX_CONVERSATION_DOCUMENT_TASKS = 100;
const POLL_DELAY_MS = 2000;

const countActiveDocuments = (payload: RagDocumentsResponse): number => {
    const statusCountsValue = payload.statusCounts;
    let activeCount = 0;
    for (const status of ACTIVE_DOCUMENT_STATUSES) {
        const countValue = statusCountsValue[status];
        if (!isNumber(countValue) || !Number.isInteger(countValue) || countValue < 0) {
            throw new Error(`RAG document list status count is invalid for ${status}`);
        }
        activeCount += Math.trunc(countValue);
    }
    return activeCount;
};

class RagIngestionQueuePacer {
    #fetchDocuments: RagDocumentListFetcher;
    #reservedDocumentSlots = 0;

    constructor(fetchDocuments: RagDocumentListFetcher) {
        this.#fetchDocuments = fetchDocuments;
    }

    async reserve(conversationId: string, documentCount: number, isStopped: () => boolean): Promise<RagIngestionQueueLease | null> {
        if (!Number.isInteger(documentCount) || documentCount <= 0) {
            throw new Error('RAG ingestion queue reservation requires a positive document count');
        }
        while (!isStopped()) {
            const activeDocuments = await this.#countActiveDocuments(conversationId);
            if (activeDocuments + this.#reservedDocumentSlots + documentCount <= MAX_CONVERSATION_DOCUMENT_TASKS) {
                this.#reservedDocumentSlots += documentCount;
                let released = false;
                return {
                    release: (): void => {
                        if (released) {
                            return;
                        }
                        released = true;
                        this.#reservedDocumentSlots = Math.max(0, this.#reservedDocumentSlots - documentCount);
                    }
                };
            }
            await sleepMs(POLL_DELAY_MS);
        }
        return null;
    }

    async #countActiveDocuments(conversationId: string): Promise<number> {
        const payload = await this.#fetchDocuments(conversationId, {
            limit: DOCUMENT_FETCH_LIMIT,
            offset: 0,
            includeDocuments: false
        });
        return countActiveDocuments(payload);
    }

    reset(): void {
        this.#reservedDocumentSlots = 0;
    }
}

export { RagIngestionQueuePacer };
export type { RagDocumentListFetcher, RagIngestionQueueLease };
