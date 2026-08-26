/* SoAI - Chat message attachment overflow action handler [frontend/assets/ts/features/chat/message/messageAttachmentOverflowAction.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatMessage, ConversationContract } from '@features/chat/ChatTypes.ts';
import type { AttachmentOverflowShowArguments } from '@features/chat/message/attachmentoverflowmodal/showArgs.ts';
import type { MessageSegment } from '@features/chat/message/messageSegments.ts';
import { isUserMessageRole } from '@features/chat/message/messageRole.ts';

interface MessageAttachmentOverflowActionDependencies {
    resolveMessageContentSegments: (message: ChatMessage) => MessageSegment[];
    showAttachmentOverflowModal: (inputArguments: AttachmentOverflowShowArguments) => void;
}

const openMessageAttachmentOverflow = (dependencies: MessageAttachmentOverflowActionDependencies, conversation: ConversationContract, message: ChatMessage, knowledgeAttachmentId: string | null | undefined): void => {
    if (!isUserMessageRole(message)) {
        return;
    }
    const conversationId = typeof conversation.id === 'string' ? conversation.id.trim() : '';
    if (!conversationId) {
        throw new Error('Attachment overflow requires a conversation id');
    }
    dependencies.showAttachmentOverflowModal({
        source: 'message',
        conversationId,
        segments: dependencies.resolveMessageContentSegments(message),
        knowledgeAttachmentId: knowledgeAttachmentId ?? null
    });
};

export { openMessageAttachmentOverflow };
export type { MessageAttachmentOverflowActionDependencies };
