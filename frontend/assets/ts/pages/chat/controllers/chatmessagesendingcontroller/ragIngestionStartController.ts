/* SoAI - Chat message sending RAG ingestion start controller [frontend/assets/ts/pages/chat/controllers/chatmessagesendingcontroller/ragIngestionStartController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireChatRagIngestionService } from '@core/chat/ragIngestionServiceAccess.ts';
import type { Conversation } from '@features/chat/public.ts';
import type { MessageSendingHost, StartRagIngestionArguments } from '@pages/chat/controllers/chatmessagesendingcontroller/types.ts';

const startRagIngestionForMessageSending = async (host: MessageSendingHost, inputArguments: StartRagIngestionArguments): Promise<void> => {
    const conversation: Conversation = {
        ...inputArguments.conversation,
        messageCount: inputArguments.conversation.history?.totalCount ?? inputArguments.conversation.messageCount ?? inputArguments.conversation.messages.length
    };
    await host.services.getConversationManager().ensureConversationPersisted(conversation);
    await requireChatRagIngestionService().start({
        conversationId: inputArguments.conversationId,
        files: inputArguments.files,
        attachmentSource: inputArguments.attachmentSource
    });
};

export { startRagIngestionForMessageSending };
export type { StartRagIngestionArguments };
