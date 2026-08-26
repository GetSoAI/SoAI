/* SoAI - Chat physical attachment draft restore mapper [frontend/assets/ts/features/chat/attachments/chatAttachmentFromPhysicalRecord.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ChatAttachment } from '@features/chat/ChatTypes.ts';
import { decodePhysicalAttachmentRecord } from '@core/realtime/eventcontracts/attachmentContracts.ts';
import { applyPhysicalAttachmentPayloadToChatAttachment } from '@features/chat/attachments/physicalAttachmentPayload.ts';

const chatAttachmentFromPhysicalRecord = (conversationId: string, record: JsonValue | null | undefined): ChatAttachment => {
    const payload = decodePhysicalAttachmentRecord(record);
    if (payload.parseState !== 'ready' || payload.state !== 'staged') {
        throw new Error('Draft physical attachment is not restorable.');
    }
    const attachment: ChatAttachment = {
        id: payload.clientAttachmentId,
        file: null,
        name: payload.filename,
        size: payload.sizeBytes,
        type: payload.mimeType,
        isImage: payload.previewType === 'image',
        parseStatus: 'ready'
    };
    applyPhysicalAttachmentPayloadToChatAttachment(attachment, conversationId, payload);
    return attachment;
};

export { chatAttachmentFromPhysicalRecord };
