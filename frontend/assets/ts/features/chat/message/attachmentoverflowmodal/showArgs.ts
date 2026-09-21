/* SoAI - Chat attachment overflow modal show argument contracts [frontend/assets/ts/features/chat/message/attachmentoverflowmodal/showArgs.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { MessageSegment } from '@features/chat/message/messageSegments.ts';

type AttachmentOverflowShowArguments = {
    source: 'message';
    conversationId: string;
    segments: readonly MessageSegment[];
    knowledgeAttachmentId?: string | null;
};

export type { AttachmentOverflowShowArguments };
