/* SoAI - Linked knowledge client batch ID construction [frontend/assets/ts/features/chat/attachments/linkedKnowledgeClientBatchId.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { computeHash } from '@core/primitives/hash.ts';

type LinkedKnowledgeClientBatchSelection = {
    itemId: number;
    documentId: string | null;
};

const LINKED_KNOWLEDGE_CLIENT_BATCH_HASH_PARTS = 4;

const createLinkedKnowledgeClientBatchId = (inputArguments: { targetConversationId: string; sourceConversationId: string; sourceKnowledgeAttachmentId: string; selections: readonly LinkedKnowledgeClientBatchSelection[] }): string => {
    const selectionSignature = [...inputArguments.selections]
        .sort((left, right) => left.itemId - right.itemId || String(left.documentId ?? '').localeCompare(String(right.documentId ?? ''), 'en'))
        .map((selection) => `${String(selection.itemId)}:${selection.documentId ?? ''}`)
        .join('\n');
    const signature = [inputArguments.targetConversationId, inputArguments.sourceConversationId, inputArguments.sourceKnowledgeAttachmentId, selectionSignature].join('\n');
    const hashParts: string[] = [];
    for (let index = 0; index < LINKED_KNOWLEDGE_CLIENT_BATCH_HASH_PARTS; index += 1) {
        hashParts.push(
            computeHash(`${String(index)}\n${signature}`)
                .toString(36)
                .padStart(7, '0')
        );
    }
    return `lk-${hashParts.join('')}`;
};

export { createLinkedKnowledgeClientBatchId };
export type { LinkedKnowledgeClientBatchSelection };
