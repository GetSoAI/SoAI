/* SoAI - Chat attachment overflow modal show argument contracts [frontend/assets/ts/features/chat/message/attachmentoverflowmodal/showArgs.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AttachmentOverflowRecord } from '@features/chat/message/attachmentoverflowmodal/records.ts';
import type { MessageSegment } from '@features/chat/message/messageSegments.ts';

type MessageAttachmentOverflowShowArguments = {
    source: 'message';
    conversationId: string;
    segments: readonly MessageSegment[];
    knowledgeAttachmentId?: string | null;
};

type RecordAttachmentOverflowShowArguments = {
    source: 'records';
    conversationId: string;
    records: readonly AttachmentOverflowRecord[];
    knowledgeAttachmentId?: string | null;
};

type AttachmentOverflowShowArguments = MessageAttachmentOverflowShowArguments | RecordAttachmentOverflowShowArguments;

export type { AttachmentOverflowShowArguments };
