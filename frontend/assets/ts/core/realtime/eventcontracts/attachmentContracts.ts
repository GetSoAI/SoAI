/* SoAI - Frontend attachment WebSocket event contracts [frontend/assets/ts/core/realtime/eventcontracts/attachmentContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { defineWebSocketEventContract } from '@core/realtime/eventcontracts/contracts.ts';
import { decodeKnowledgeAttachmentChangedEvent, type KnowledgeAttachmentSummary } from '@core/api/contracts/webuiAttachmentContracts.ts';
import { readRequiredFiniteNumberValue, readRequiredNonNegativeIntegerValue, readRequiredPositiveIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableTrimmedStringValue, readOptionalBooleanValue, readRequiredEnumValue, readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { WEBSOCKET_EVENT_TYPES } from '@core/websocketEvents.ts';

type PhysicalAttachmentParseState = 'failed' | 'pending' | 'ready';
interface PhysicalAttachmentPayload {
    clientAttachmentId: string;
    attachmentId: string;
    fileId: string;
    filename: string;
    mimeType: string;
    sizeBytes: number;
    previewType: string;
    providerMode: string | null;
    providerTextTruncated: boolean;
    parseState: PhysicalAttachmentParseState;
    parseError: string | null;
    state: string;
    attachmentRevision: number;
    createdAtMs: number;
    updatedAtMs: number;
    previewUrl: string | null;
    downloadUrl: string | null;
}
interface ConversationAttachmentChangedEvent {
    eventId: string;
    timestamp: number;
    userId: number;
    convId: string;
    attachmentId: string;
    clientAttachmentId: string | null;
    parseState: PhysicalAttachmentParseState;
    state: string;
    attachmentRevision: number;
    updatedAtMs: number;
    attachment: PhysicalAttachmentPayload;
}

const decodePhysicalAttachmentRecord = (value: JsonValue | undefined): PhysicalAttachmentPayload => {
    const record = requireRecord(value, 'Physical attachment');
    return {
        clientAttachmentId: readRequiredTrimmedStringValue(record['client_attachment_id'], 'Physical attachment.client_attachment_id'),
        attachmentId: readRequiredTrimmedStringValue(record['attachment_id'], 'Physical attachment.attachment_id'),
        fileId: readRequiredTrimmedStringValue(record['file_id'], 'Physical attachment.file_id'),
        filename: readRequiredTrimmedStringValue(record['filename'], 'Physical attachment.filename'),
        mimeType: readRequiredTrimmedStringValue(record['mime_type'], 'Physical attachment.mime_type'),
        sizeBytes: readRequiredNonNegativeIntegerValue(record['size_bytes'], 'Physical attachment.size_bytes'),
        previewType: readRequiredTrimmedStringValue(record['preview_type'], 'Physical attachment.preview_type'),
        providerMode: readNullableTrimmedStringValue(record['provider_mode'], 'Physical attachment.provider_mode'),
        providerTextTruncated: readOptionalBooleanValue(record['provider_text_truncated'], 'Physical attachment.provider_text_truncated') ?? false,
        parseState: readRequiredEnumValue(record['parse_state'], 'Physical attachment.parse_state', ['failed', 'pending', 'ready']),
        parseError: readNullableTrimmedStringValue(record['parse_error'], 'Physical attachment.parse_error'),
        state: readRequiredTrimmedStringValue(record['state'], 'Physical attachment.state'),
        attachmentRevision: readRequiredNonNegativeIntegerValue(record['attachment_revision'], 'Physical attachment.attachment_revision'),
        createdAtMs: readRequiredNonNegativeIntegerValue(record['created_at_ms'], 'Physical attachment.created_at_ms'),
        updatedAtMs: readRequiredNonNegativeIntegerValue(record['updated_at_ms'], 'Physical attachment.updated_at_ms'),
        previewUrl: readNullableTrimmedStringValue(record['preview_url'], 'Physical attachment.preview_url'),
        downloadUrl: readNullableTrimmedStringValue(record['download_url'], 'Physical attachment.download_url')
    };
};

const decodeConversationAttachmentChanged = (payload: JsonValue): ConversationAttachmentChangedEvent => {
    const record = requireRecord(payload, 'Conversation attachment changed event');
    const attachment = decodePhysicalAttachmentRecord(record['attachment']);
    const timestamp = readRequiredFiniteNumberValue(record['timestamp'], 'Conversation attachment changed event.timestamp');
    const decoded = {
        eventId: readRequiredTrimmedStringValue(record['event_id'], 'Conversation attachment changed event.event_id'),
        timestamp,
        userId: readRequiredPositiveIntegerValue(record['user_id'], 'Conversation attachment changed event.user_id'),
        convId: readRequiredTrimmedStringValue(record['conv_id'], 'Conversation attachment changed event.conv_id'),
        attachmentId: readRequiredTrimmedStringValue(record['attachment_id'], 'Conversation attachment changed event.attachment_id'),
        clientAttachmentId: readNullableTrimmedStringValue(record['client_attachment_id'], 'Conversation attachment changed event.client_attachment_id'),
        parseState: readRequiredEnumValue(record['parse_state'], 'Conversation attachment changed event.parse_state', ['failed', 'pending', 'ready']),
        state: readRequiredTrimmedStringValue(record['state'], 'Conversation attachment changed event.state'),
        attachmentRevision: readRequiredNonNegativeIntegerValue(record['attachment_revision'], 'Conversation attachment changed event.attachment_revision'),
        updatedAtMs: readRequiredNonNegativeIntegerValue(record['updated_at_ms'], 'Conversation attachment changed event.updated_at_ms'),
        attachment
    };
    if (timestamp <= 0) throw new TypeError('Conversation attachment changed event.timestamp must be positive');
    if (decoded.attachmentId !== attachment.attachmentId || decoded.clientAttachmentId !== attachment.clientAttachmentId || decoded.parseState !== attachment.parseState || decoded.state !== attachment.state || decoded.attachmentRevision !== attachment.attachmentRevision || decoded.updatedAtMs !== attachment.updatedAtMs) throw new TypeError('Conversation attachment changed event envelope does not match attachment');
    return decoded;
};

const ATTACHMENT_EVENT_CONTRACTS = Object.freeze({
    conversationChanged: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.CONVERSATION_ATTACHMENT_CHANGED, decodeConversationAttachmentChanged),
    knowledgeChanged: defineWebSocketEventContract<KnowledgeAttachmentSummary>(WEBSOCKET_EVENT_TYPES.KNOWLEDGE_ATTACHMENT_CHANGED, decodeKnowledgeAttachmentChangedEvent)
});

export { ATTACHMENT_EVENT_CONTRACTS, decodePhysicalAttachmentRecord };
export type { ConversationAttachmentChangedEvent, PhysicalAttachmentParseState, PhysicalAttachmentPayload };
