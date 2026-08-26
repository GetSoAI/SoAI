/* SoAI - Conversation metadata operation dependencies [frontend/assets/ts/features/chat/conversation/conversationMetadataOperationDeps.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatPageApi } from '@features/chat/pagecontracts/types.ts';
import type { ConversationMutationSequencer } from '@features/chat/conversation/conversationMutationSequencing.ts';
import type { Conversation } from '@features/chat/storage/storageModels.ts';

interface ConversationMetadataOperationDependencies {
    chatApi: ChatPageApi['webui']['chat'];
    conversations: Map<string, Conversation>;
    ensureConversationPersisted: (conversation: Conversation) => Promise<void>;
    getCurrentConversationId: () => string | null;
    markConversationPersisted: (conversationId: string) => void;
    mutationSequencer: ConversationMutationSequencer;
}

export type { ConversationMetadataOperationDependencies };
