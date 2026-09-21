/* SoAI - Chat attachment overflow modal record mapping [frontend/assets/ts/features/chat/message/attachmentoverflowmodal/records.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildWebuiConversationAttachmentContentPath, buildWebuiConversationAttachmentThumbnailPath, buildWebuiConversationSoaiPathThumbnailPath } from '@core/api/endpoints/webuiConversationPaths.ts';
import { formatBytes } from '@core/primitives/byteSize.ts';
import { i18n } from '@core/i18n/index.ts';
import { resolveFileEntryIconName } from '@core/fileexplorerbrowser/entryIconResolution.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { cloneSoaiPathStoragePart, type SoaiPathStoragePart } from '@features/chat/attachments/soaiPathContentPart.ts';
import type { MessageSegment } from '@features/chat/message/messageSegments.ts';
import { isAttachmentSummarySegment } from '@features/chat/message/messageview/attachmentSummaryCards.ts';

type AttachmentOverflowRecord = {
    id: string;
    type: 'attachment' | 'knowledge' | 'soaiLink' | 'knowledgeItem';
    title: string;
    status: string;
    href: string | null;
    knowledgeAttachmentId: string | null;
    knowledgeItemId: number | null;
    documentId: string | null;
    unavailableReason: string | null;
    previewUrl: string | null;
    soaiPathContentPart: SoaiPathStoragePart | null;
    iconName: IconName;
};

const resolveSegmentRecord = (conversationId: string, segment: MessageSegment, index: number): AttachmentOverflowRecord | null => {
    if (segment.type === 'soai_file_unavailable') {
        return {
            id: `unavailable-file:${String(index)}`,
            type: 'attachment',
            title: segment.filename,
            status: `${segment.mimeType} - ${formatBytes(segment.sizeBytes, 1)}`,
            href: null,
            knowledgeAttachmentId: null,
            knowledgeItemId: null,
            documentId: null,
            unavailableReason: i18n.t('chat.inlinePreviews.typeLabel.unavailable'),
            previewUrl: null,
            soaiPathContentPart: null,
            iconName: resolveFileEntryIconName({ name: segment.filename, mimeType: segment.mimeType, isDirectory: false })
        };
    }
    if (segment.type === 'soai_file') {
        return {
            id: `file:${segment.attachmentId}:${String(index)}`,
            type: 'attachment',
            title: segment.filename,
            status: `${segment.mimeType} - ${formatBytes(segment.sizeBytes, 1)}`,
            href: buildWebuiConversationAttachmentContentPath(conversationId, segment.attachmentId, true),
            knowledgeAttachmentId: null,
            knowledgeItemId: null,
            documentId: null,
            unavailableReason: null,
            previewUrl: segment.previewType === 'image' ? buildWebuiConversationAttachmentThumbnailPath(conversationId, segment.attachmentId) : null,
            soaiPathContentPart: null,
            iconName: resolveFileEntryIconName({ name: segment.filename, mimeType: segment.mimeType, isDirectory: false })
        };
    }
    if (segment.type === 'image') {
        return {
            id: `image:${segment.imageUrl}:${String(index)}`,
            type: 'attachment',
            title: segment.title,
            status: '',
            href: segment.imageUrl,
            knowledgeAttachmentId: null,
            knowledgeItemId: null,
            documentId: null,
            unavailableReason: null,
            previewUrl: segment.imageUrl,
            soaiPathContentPart: null,
            iconName: resolveFileEntryIconName({ name: segment.title, mimeType: 'image/*', isDirectory: false })
        };
    }
    if (segment.type === 'soai_path') {
        return {
            id: `path:${segment.virtualPath}:${String(index)}`,
            type: 'soaiLink',
            title: segment.title,
            status: segment.virtualPath,
            href: null,
            knowledgeAttachmentId: null,
            knowledgeItemId: null,
            documentId: null,
            unavailableReason: null,
            previewUrl: segment.entryType === 'file' && segment.previewType === 'image' ? buildWebuiConversationSoaiPathThumbnailPath(conversationId, segment.contentPart) : null,
            soaiPathContentPart: cloneSoaiPathStoragePart(segment.contentPart),
            iconName: resolveFileEntryIconName({ name: segment.title, mimeType: segment.mimeType ?? segment.contentPart.mimeType, isDirectory: segment.entryType === 'folder' })
        };
    }
    if (segment.type === 'soai_knowledge') {
        const isLinkedKnowledge = segment.sourceType === 'linked_knowledge';
        return {
            id: `knowledge:${segment.knowledgeAttachmentId}:${String(index)}`,
            type: 'knowledge',
            title: segment.title,
            status: `${String(segment.visibleCount)} / ${String(segment.totalCount)}`,
            href: null,
            knowledgeAttachmentId: isLinkedKnowledge ? null : segment.knowledgeAttachmentId,
            knowledgeItemId: null,
            documentId: null,
            unavailableReason: null,
            previewUrl: null,
            soaiPathContentPart: null,
            iconName: 'file-database'
        };
    }
    if (segment.type === 'soai_knowledge_unavailable') {
        return {
            id: `unavailable-knowledge:${String(index)}`,
            type: 'knowledge',
            title: segment.title,
            status: '',
            href: null,
            knowledgeAttachmentId: null,
            knowledgeItemId: null,
            documentId: null,
            unavailableReason: i18n.t('chat.inlinePreviews.typeLabel.unavailable'),
            previewUrl: null,
            soaiPathContentPart: null,
            iconName: 'file-database'
        };
    }
    return null;
};

const buildAttachmentOverflowRecords = (conversationId: string, segments: readonly MessageSegment[]): AttachmentOverflowRecord[] => {
    const records: AttachmentOverflowRecord[] = [];
    for (const [index, segment] of segments.entries()) {
        if (!isAttachmentSummarySegment(segment)) {
            continue;
        }
        const record = resolveSegmentRecord(conversationId, segment, index);
        if (record !== null) {
            records.push(record);
        }
    }
    return records;
};

export { buildAttachmentOverflowRecords };
export type { AttachmentOverflowRecord };
