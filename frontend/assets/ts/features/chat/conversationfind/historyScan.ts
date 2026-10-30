/* SoAI - Bounded operation-local conversation find history scanning [frontend/assets/ts/features/chat/conversationfind/historyScan.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { scanLiteralOccurrences, type LiteralSearchQuery } from '@core/search/literalOccurrences.ts';
import { SearchWorkBudget } from '@core/search/searchWorkBudget.ts';
import { createConversationFindEntry } from '@features/chat/message/messageRenderSignature.ts';
import type { ConversationFindEntry } from '@features/chat/conversationfind/contracts.ts';
import { resolveConversationFindMessages } from '@features/chat/conversationfind/searchMessages.ts';
import { CONVERSATION_FIND_MESSAGE_LIMIT, ConversationFindResultIndex } from '@features/chat/conversationfind/searchResults.ts';
import { resolvePersistedMessageCursor } from '@features/chat/message/persistedMessageIdentity.ts';
import type { MessageSearchTextProjection } from '@features/chat/message/searchTextProjection.ts';
import { visitConversationSnapshot, type ConversationSnapshotMetadata, type ConversationSnapshotReader } from '@features/chat/storage/conversationSnapshotLoading.ts';
import type { MessageCursor } from '@features/chat/storage/storageModels.ts';

interface ConversationFindScanResult extends ConversationSnapshotMetadata {
    index: ConversationFindResultIndex;
    truncated: boolean;
    oldestScannedCursor: MessageCursor | null;
}

interface ConversationFindScanOptions {
    conversationId: string;
    query: LiteralSearchQuery;
    documentRef: Document;
    projection: MessageSearchTextProjection;
    signal: AbortSignal;
}

const scanConversationFindHistory = async (manager: ConversationSnapshotReader, options: ConversationFindScanOptions): Promise<ConversationFindScanResult> => {
    if (!options.query.foldedText) throw new Error('Conversation search requires a nonempty query');
    const budget = new SearchWorkBudget(options.documentRef.defaultView, options.signal);
    const projectMessageText = options.projection;
    const matches: ConversationFindEntry[] = [];
    let truncated = false;
    let oldestScannedCursor: MessageCursor | null = null;
    const metadata = await visitConversationSnapshot(manager, options.conversationId, {
        pageLimit: 25,
        signal: options.signal,
        verifyFreshness: true,
        visitPage: async (messages) => {
            await budget.checkpoint(true);
            const orderedMessages = resolveConversationFindMessages(messages);
            for (let index = orderedMessages.length - 1; index >= 0; index -= 1) {
                const candidate = orderedMessages[index];
                if (!candidate) continue;
                await budget.checkpoint();
                let count = 0;
                await projectMessageText(candidate.message, budget, async (block) => {
                    const result = await scanLiteralOccurrences(block.text, options.query, budget);
                    count += result.count;
                    return true;
                });
                oldestScannedCursor = resolvePersistedMessageCursor(candidate.message);
                if (count === 0) continue;
                if (matches.length === CONVERSATION_FIND_MESSAGE_LIMIT) {
                    truncated = true;
                    return false;
                }
                matches.push(createConversationFindEntry(candidate.message, count, candidate.orderMessage));
            }
            return true;
        }
    });
    return { totalCount: metadata.totalCount, revision: metadata.revision, visitedCount: metadata.visitedCount, index: new ConversationFindResultIndex(matches), truncated, oldestScannedCursor };
};

export { scanConversationFindHistory };
export type { ConversationFindScanOptions, ConversationFindScanResult };
