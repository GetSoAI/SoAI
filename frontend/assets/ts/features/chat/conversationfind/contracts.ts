/* SoAI - Conversation find metadata contracts [frontend/assets/ts/features/chat/conversationfind/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AssistantVariantIdentity } from '@core/chat/assistantIdentity.ts';
import type { MessageCursor } from '@features/chat/storage/storageModels.ts';

interface ConversationFindEntry {
    readonly messageId: string;
    readonly semanticId: string;
    readonly cursor: MessageCursor | null;
    readonly comparison: AssistantVariantIdentity | null;
    readonly count: number;
    readonly sourceRevision: string;
    readonly orderCursor: MessageCursor | null;
    readonly orderTimestamp: number;
}

interface ConversationFindTarget {
    messageId: string;
    occurrenceIndex: number;
}

interface ConversationFindOverride {
    entry: ConversationFindEntry;
    baselineSourceRevision: string | null;
    mounted: boolean;
}

export type { ConversationFindEntry, ConversationFindOverride, ConversationFindTarget };
