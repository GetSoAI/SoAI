/* SoAI - Canonical attachment OpenAI content fragment mapping [frontend/assets/ts/features/chat/attachments/attachmentContentFragments.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildSoaiFileContentPartFromAttachment } from '@features/chat/attachments/soaiFileContentPart.ts';
import { cloneSoaiPathDraftRecordContentPart, isSoaiPathDraftRecord } from '@features/chat/attachments/soaiPathDraftRecords.ts';
import { isChatAttachmentReadyForSend } from '@features/chat/ChatAttachmentSupport.ts';
import type { ChatAttachment, ChatContentSegment } from '@features/chat/ChatTypes.ts';

type ContentFragment = ChatContentSegment;

const buildChatAttachmentContentFragmentsFromAttachments = (attachments: readonly ChatAttachment[]): ContentFragment[] => {
    const fragments: ContentFragment[] = [];
    for (const attachment of attachments) {
        if (!isChatAttachmentReadyForSend(attachment)) {
            continue;
        }
        if (isSoaiPathDraftRecord(attachment.soaiPathRecord)) {
            fragments.push(cloneSoaiPathDraftRecordContentPart(attachment.soaiPathRecord));
            continue;
        }
        fragments.push(buildSoaiFileContentPartFromAttachment(attachment));
    }
    return fragments;
};

export { buildChatAttachmentContentFragmentsFromAttachments };
export type { ContentFragment };
