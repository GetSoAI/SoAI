/* SoAI - Chat draft attachment presentation resolution [frontend/assets/ts/features/chat/attachments/draftAttachmentPresentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveFileEntryIconName } from '@core/fileexplorerbrowser/entryIconResolution.ts';
import { i18n } from '@core/i18n/index.ts';
import { isSoaiPathDraftRecord } from '@features/chat/attachments/soaiPathDraftRecords.ts';
import type { ChatAttachment } from '@features/chat/ChatTypes.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';

const resolveDraftAttachmentIconName = (attachment: ChatAttachment): IconName => {
    const record = attachment.soaiPathRecord;
    return resolveFileEntryIconName({
        name: attachment.name,
        mimeType: isSoaiPathDraftRecord(record) ? record.contentPart.mimeType : (attachment.mimeType ?? attachment.type),
        isDirectory: isSoaiPathDraftRecord(record) && record.contentPart.entryType === 'folder'
    });
};

const resolveDraftAttachmentStatusLabel = (status: ChatAttachment['parseStatus']): string => {
    if (status === 'ready') {
        return i18n.t('chat.attachments.status.ready');
    }
    if (status === 'processing') {
        return i18n.t('chat.attachments.status.processing');
    }
    return i18n.t('chat.attachments.status.error');
};

export { resolveDraftAttachmentIconName, resolveDraftAttachmentStatusLabel };
