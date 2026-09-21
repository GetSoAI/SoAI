/* SoAI - Chat physical attachment payload mapping [frontend/assets/ts/features/chat/attachments/physicalAttachmentPayload.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PhysicalAttachmentResponse } from '@core/api/contracts/webuiAttachmentContracts.ts';
import type { PhysicalAttachmentParseState, PhysicalAttachmentPayload } from '@core/realtime/eventcontracts/attachmentContracts.ts';
import { isNonNegativeInteger } from '@core/typeGuards.ts';
import type { ChatAttachment } from '@features/chat/ChatTypes.ts';

const requireParseState = (value: string): PhysicalAttachmentParseState => {
    if (value === 'pending' || value === 'ready' || value === 'failed') {
        return value;
    }
    throw new Error('Physical attachment payload has invalid parse_state.');
};

const requireClientAttachmentId = (value: string | null): string => {
    if (value === null || !value.trim()) throw new Error('Physical attachment payload is missing client_attachment_id.');
    return value.trim();
};

const mapPhysicalAttachmentResponse = (response: PhysicalAttachmentResponse): PhysicalAttachmentPayload => ({
    clientAttachmentId: requireClientAttachmentId(response.clientAttachmentId),
    attachmentId: response.attachmentId,
    fileId: response.fileId,
    filename: response.filename,
    mimeType: response.mimeType,
    sizeBytes: response.sizeBytes,
    previewType: response.previewType,
    providerMode: response.providerMode,
    providerTextTruncated: response.providerTextTruncated ?? false,
    parseState: requireParseState(response.parseState),
    parseError: response.parseError,
    state: response.state,
    attachmentRevision: response.attachmentRevision,
    createdAtMs: response.createdAtMs,
    updatedAtMs: response.updatedAtMs,
    previewUrl: response.previewUrl,
    downloadUrl: response.downloadUrl
});

const applyPhysicalAttachmentPayloadToChatAttachment = (attachment: ChatAttachment, conversationId: string, payload: PhysicalAttachmentPayload): boolean => {
    const currentRevision = attachment.attachmentRevision;
    if (isNonNegativeInteger(currentRevision) && payload.attachmentRevision < currentRevision) {
        return false;
    }
    attachment.conversationId = conversationId;
    attachment.clientAttachmentId = payload.clientAttachmentId;
    attachment.attachmentId = payload.attachmentId;
    attachment.fileId = payload.fileId;
    attachment.name = payload.filename;
    attachment.size = payload.sizeBytes;
    attachment.type = payload.mimeType;
    attachment.mimeType = payload.mimeType;
    attachment.sizeBytes = payload.sizeBytes;
    attachment.previewType = payload.previewType;
    attachment.isImage = payload.previewType === 'image';
    attachment.providerMode = payload.providerMode;
    attachment.providerTextTruncated = payload.providerTextTruncated;
    attachment.parseState = payload.parseState;
    attachment.state = payload.state;
    attachment.attachmentRevision = payload.attachmentRevision;
    attachment.createdAtMs = payload.createdAtMs;
    attachment.updatedAtMs = payload.updatedAtMs;
    attachment.parseError = payload.parseError ?? '';
    if (payload.previewUrl !== null) {
        attachment.previewUrl = payload.previewUrl;
    }
    if (payload.downloadUrl !== null) {
        attachment.downloadUrl = payload.downloadUrl;
    }
    attachment.parseStatus = payload.parseState === 'ready' ? 'ready' : payload.parseState === 'failed' ? 'error' : 'processing';
    return true;
};

export { applyPhysicalAttachmentPayloadToChatAttachment, mapPhysicalAttachmentResponse };
