/* SoAI - Effective chat attachment draft source resolution [frontend/assets/ts/features/chat/attachments/chatAttachmentDraftSource.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatAttachment, ChatAttachmentDraftSource } from '@features/chat/ChatTypes.ts';
import { isSoaiPathDraftRecord } from '@features/chat/attachments/soaiPathDraftRecords.ts';

const resolveChatAttachmentDraftSource = (attachment: ChatAttachment): ChatAttachmentDraftSource => {
    if (isSoaiPathDraftRecord(attachment.soaiPathRecord)) {
        return attachment.draftSource === 'browse' ? 'browse' : 'soaiLink';
    }
    return attachment.draftSource === 'camera' ? 'camera' : 'upload';
};

export { resolveChatAttachmentDraftSource };
