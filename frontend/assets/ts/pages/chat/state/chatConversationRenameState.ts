/* SoAI - Chat page conversation rename state [frontend/assets/ts/pages/chat/state/chatConversationRenameState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type ChatConversationRenameScope = 'header' | 'sidebar';

type ChatConversationRenameState = {
    scope: ChatConversationRenameScope;
    conversationId: string;
    originalTitle: string;
    draft: string;
};

export type { ChatConversationRenameScope, ChatConversationRenameState };
