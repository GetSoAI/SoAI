/* SoAI - Conversation find search session contracts [frontend/assets/ts/pages/chat/controllers/conversationfind/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ResourceTracker } from '@core/resourcetracker/service.ts';
import type { LiteralSearchQuery } from '@core/search/literalOccurrences.ts';
import type { ConversationFindResultIndex, ConversationFindScanResult, ConversationFindTarget } from '@features/chat/public.ts';

interface ConversationFindSearchContext {
    conversationId: string;
    revision: number;
    presentationKey: string;
    executionActive: boolean;
    signal: AbortSignal;
    isCurrent(): boolean;
}

type ConversationFindSearchStatus = 'idle' | 'scanning' | 'ready' | 'updating' | 'stale' | 'incomplete' | 'error' | 'too-long';

interface ConversationFindSearchSnapshot {
    open: boolean;
    query: string;
    status: ConversationFindSearchStatus;
    showSearching: boolean;
    index: ConversationFindResultIndex;
    target: ConversationFindTarget | null;
    truncated: boolean;
    needsRefill: boolean;
    verifiedAt: number | null;
    failure: 'deadline' | 'conflict' | 'operation' | null;
}

interface ConversationFindSearchDependencies {
    resources: Pick<ResourceTracker, 'setTimeout' | 'clearTimer'>;
    captureContext(): ConversationFindSearchContext | null;
    scan(query: LiteralSearchQuery, signal: AbortSignal): Promise<ConversationFindScanResult>;
    runTask(operationId: string, operation: () => Promise<void>): void;
    onChanged(): void;
    onInvalidated(): void;
    reportFailure(error: Error): void;
}

export type { ConversationFindSearchContext, ConversationFindSearchDependencies, ConversationFindSearchSnapshot, ConversationFindSearchStatus };
