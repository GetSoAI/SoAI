/* SoAI - Draft chat attachment overflow record mapping [frontend/assets/ts/features/chat/attachments/draftAttachmentOverflowRecords.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildWebuiConversationAttachmentContentPath, buildWebuiConversationAttachmentThumbnailPath } from '@core/api/endpoints/webuiConversationPaths.ts';
import type { KnowledgeAttachmentSummary } from '@core/api/contracts/webuiAttachmentContracts.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedStringOrNull } from '@core/normalize.ts';
import { formatBytes } from '@core/primitives/byteSize.ts';
import { isNumber } from '@core/typeGuards.ts';
import { appendPhysicalAttachmentProviderStatus } from '@features/chat/attachments/physicalAttachmentProviderStatus.ts';
import { cloneSoaiPathDraftRecordContentPart, isSoaiPathDraftRecord, requireSoaiPathDraftRecordVirtualPath, resolveSoaiPathDraftRecordTitle, type SoaiPathDraftRecord } from '@features/chat/attachments/soaiPathDraftRecords.ts';
import type { ChatAttachment } from '@features/chat/ChatTypes.ts';
import type { RagIngestionStatus } from '@features/chat/ingestion/types.ts';
import type { AttachmentOverflowRecord } from '@features/chat/message/attachmentoverflowmodal/records.ts';

type DraftAttachmentOverflowArguments = {
    conversationId: string;
    attachments: readonly ChatAttachment[];
    knowledgeDrafts: readonly KnowledgeAttachmentSummary[];
    ingestionStatus: RagIngestionStatus | null;
};

const isTerminalKnowledgeState = (value: string | null): boolean => {
    return value === 'ready' || value === 'error' || value === 'cancelled';
};

const buildPhysicalDraftRecord = (conversationId: string, attachment: ChatAttachment, index: number): AttachmentOverflowRecord => {
    const attachmentId = toTrimmedStringOrNull(attachment.attachmentId);
    const mimeType = toTrimmedStringOrNull(attachment.mimeType) ?? toTrimmedStringOrNull(attachment.type) ?? '';
    const sizeBytes = isNumber(attachment.sizeBytes) && Number.isFinite(attachment.sizeBytes) ? Math.max(0, Math.trunc(attachment.sizeBytes)) : Math.max(0, Math.trunc(attachment.size));
    const href = toTrimmedStringOrNull(attachment.downloadUrl) ?? (attachmentId === null ? null : buildWebuiConversationAttachmentContentPath(conversationId, attachmentId, true));
    const previewUrl = attachment.isImage ? (toTrimmedStringOrNull(attachment.previewUrl) ?? (attachmentId === null ? null : buildWebuiConversationAttachmentThumbnailPath(conversationId, attachmentId))) : null;
    const baseStatus = mimeType ? `${mimeType} - ${formatBytes(sizeBytes, 1)}` : attachment.parseStatus;
    return {
        id: `draft-file:${attachment.id}:${String(index)}`,
        type: 'attachment',
        title: attachment.name,
        status: appendPhysicalAttachmentProviderStatus(attachment, baseStatus),
        draftRemovable: false,
        href,
        knowledgeAttachmentId: null,
        knowledgeItemId: null,
        documentId: null,
        unavailableReason: null,
        previewUrl,
        soaiPathContentPart: null
    };
};

const buildSoaiPathDraftRecord = (record: SoaiPathDraftRecord, index: number): AttachmentOverflowRecord => {
    const virtualPath = requireSoaiPathDraftRecordVirtualPath(record);
    return {
        id: `draft-path:${virtualPath}:${String(index)}`,
        type: 'soaiLink',
        title: resolveSoaiPathDraftRecordTitle(record),
        status: virtualPath,
        draftRemovable: false,
        href: null,
        knowledgeAttachmentId: null,
        knowledgeItemId: null,
        documentId: null,
        unavailableReason: null,
        previewUrl: null,
        soaiPathContentPart: cloneSoaiPathDraftRecordContentPart(record)
    };
};

const buildKnowledgeDraftRecord = (knowledge: KnowledgeAttachmentSummary, index: number, includeNonTerminal: boolean): AttachmentOverflowRecord | null => {
    const processingState = knowledge.processingState;
    if (!includeNonTerminal && !isTerminalKnowledgeState(processingState)) {
        return null;
    }
    const knowledgeAttachmentId = knowledge.knowledgeAttachmentId;
    const title = knowledge.title || knowledge.rootLabel || i18n.t('chat.ingestion.title');
    const totalCount = knowledge.totalCount;
    const visibleCount = knowledge.visibleCount;
    return {
        id: `draft-knowledge:${knowledgeAttachmentId ?? String(index)}`,
        type: 'knowledge',
        title,
        status: `${String(visibleCount)} / ${String(totalCount)}`,
        draftRemovable: true,
        href: null,
        knowledgeAttachmentId,
        knowledgeItemId: null,
        documentId: null,
        unavailableReason: null,
        previewUrl: null,
        soaiPathContentPart: null
    };
};

const buildDraftAttachmentOverflowRecords = (inputArguments: DraftAttachmentOverflowArguments): AttachmentOverflowRecord[] => {
    const records: AttachmentOverflowRecord[] = [];
    const ingestionRecord = inputArguments.ingestionStatus?.knowledgeAttachment ? buildKnowledgeDraftRecord(inputArguments.ingestionStatus.knowledgeAttachment, -1, true) : null;
    if (ingestionRecord !== null && (inputArguments.ingestionStatus?.state === 'running' || inputArguments.ingestionStatus?.state === 'paused')) {
        records.push(ingestionRecord);
    }
    for (let index = 0; index < inputArguments.knowledgeDrafts.length; index += 1) {
        const knowledgeDraft = inputArguments.knowledgeDrafts[index];
        if (!knowledgeDraft) {
            continue;
        }
        const record = buildKnowledgeDraftRecord(knowledgeDraft, index, false);
        if (record !== null) {
            records.push(record);
        }
    }
    for (let index = 0; index < inputArguments.attachments.length; index += 1) {
        const attachment = inputArguments.attachments[index];
        if (!attachment) {
            continue;
        }
        const soaiPathRecord = attachment.soaiPathRecord;
        records.push(isSoaiPathDraftRecord(soaiPathRecord) ? buildSoaiPathDraftRecord(soaiPathRecord, index) : buildPhysicalDraftRecord(inputArguments.conversationId, attachment, index));
    }
    return records;
};

export { buildDraftAttachmentOverflowRecords };
