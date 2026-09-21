/* SoAI - Chat physical image attachment preview URL resolution [frontend/assets/ts/features/chat/attachments/physicalAttachmentPreviewUrl.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildWebuiConversationAttachmentThumbnailPath } from '@core/api/endpoints/webuiConversationPaths.ts';
import { toTrimmedStringOrNull } from '@core/normalize.ts';
import type { ChatAttachment } from '@features/chat/ChatTypes.ts';

const resolvePhysicalAttachmentPreviewUrl = (conversationId: string | null, attachment: ChatAttachment): string | null => {
    if (!attachment.isImage) {
        return null;
    }
    const previewUrl = toTrimmedStringOrNull(attachment.previewUrl);
    if (previewUrl !== null) {
        return previewUrl;
    }
    const attachmentId = toTrimmedStringOrNull(attachment.attachmentId);
    const owningConversationId = toTrimmedStringOrNull(attachment.conversationId) ?? toTrimmedStringOrNull(conversationId);
    return owningConversationId === null || attachmentId === null ? null : buildWebuiConversationAttachmentThumbnailPath(owningConversationId, attachmentId);
};

export { resolvePhysicalAttachmentPreviewUrl };
