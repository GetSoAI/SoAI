/* SoAI - Chat attachment modal domain ports [frontend/assets/ts/pages/chat/controllers/modals/chatattach/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatAttachmentActionPort, ChatConversationActionPort, ChatExecutionActionPort, ChatPresentationActionPort, ChatRagActionPort, ChatSharedActionPort } from '@pages/chat/controllers/actionhandlers/core/contracts.ts';

interface ChatAttachModalHost {
    shared: ChatSharedActionPort;
    conversation: ChatConversationActionPort;
    execution: ChatExecutionActionPort;
    attachments: ChatAttachmentActionPort;
    presentation: ChatPresentationActionPort;
    rag: ChatRagActionPort;
}

type ChatAttachWorkspacePathHost = Pick<ChatAttachModalHost, 'conversation' | 'execution' | 'shared'>;
type ChatAttachDraftListHost = Pick<ChatAttachModalHost, 'attachments' | 'conversation' | 'execution'>;
type ChatAttachKnowledgeRefreshHost = Pick<ChatAttachModalHost, 'shared'>;
type ChatAttachSoaiLinkHost = Pick<ChatAttachModalHost, 'attachments' | 'conversation' | 'execution' | 'shared'>;
type ChatAttachBrowseHost = ChatAttachModalHost;
type ChatAttachBrowseKnowledgeHost = Pick<ChatAttachModalHost, 'conversation' | 'presentation' | 'rag' | 'shared'>;
type ChatAttachBrowseWorkspaceHost = Pick<ChatAttachModalHost, 'attachments' | 'conversation' | 'presentation' | 'shared'>;
type ChatAttachAvailabilityHost = Pick<ChatAttachModalHost, 'attachments'>;
type ChatAttachKnowledgeHost = Pick<ChatAttachModalHost, 'conversation' | 'execution' | 'rag' | 'shared'>;
type ChatAttachUploadHost = Pick<ChatAttachModalHost, 'attachments' | 'conversation' | 'execution' | 'shared'>;
type ChatAttachKnowledgeOperationsHost = Pick<ChatAttachModalHost, 'conversation' | 'rag' | 'shared'>;

export type { ChatAttachAvailabilityHost, ChatAttachBrowseHost, ChatAttachBrowseKnowledgeHost, ChatAttachBrowseWorkspaceHost, ChatAttachDraftListHost, ChatAttachKnowledgeHost, ChatAttachKnowledgeOperationsHost, ChatAttachKnowledgeRefreshHost, ChatAttachModalHost, ChatAttachSoaiLinkHost, ChatAttachUploadHost, ChatAttachWorkspacePathHost };
