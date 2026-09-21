/* SoAI - Chat attachment overflow modal knowledge item pagination [frontend/assets/ts/features/chat/message/attachmentoverflowmodal/knowledgeItems.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { formatBytes } from '@core/primitives/byteSize.ts';
import type { KnowledgeAttachmentItem, KnowledgeAttachmentItemsResponse } from '@core/api/contracts/webuiAttachmentContracts.ts';
import type { KnowledgeStatusFilter } from '@features/chat/message/attachmentoverflowmodal/filters.ts';
import type { AttachmentOverflowRecord } from '@features/chat/message/attachmentoverflowmodal/records.ts';
import { resolveFileEntryIconName } from '@core/fileexplorerbrowser/entryIconResolution.ts';

type KnowledgeCursor = {
    itemIndex: number;
    id: number;
};

type KnowledgeItemsPage = {
    items: AttachmentOverflowRecord[];
    nextCursor: KnowledgeCursor | null;
};

type KnowledgeItemsQuery = {
    status: KnowledgeStatusFilter | null;
    query: string | null;
};

type KnowledgeItemsRequestOptions = {
    limit: number;
    signal?: AbortSignal | undefined;
    cursorItemIndex?: number | undefined;
    cursorId?: number | undefined;
    status?: string | undefined;
    query?: string | undefined;
};

const KNOWLEDGE_PAGE_LIMIT = 50;

const parseKnowledgeCursor = (value: KnowledgeAttachmentItemsResponse['nextCursor']): KnowledgeCursor | null => (value === null ? null : { ...value });

const parseKnowledgeItemRecord = (value: KnowledgeAttachmentItem, knowledgeAttachmentId: string): AttachmentOverflowRecord => {
    const statusParts: string[] = [value.operationType];
    if (value.ragStatus !== null) {
        statusParts.push(value.ragStatus);
    }
    if (value.fileType !== null) {
        statusParts.push(value.fileType);
    }
    if (value.fileSizeBytes !== null) {
        statusParts.push(formatBytes(value.fileSizeBytes, 1));
    }
    const unavailableReason = value.errorMessage ?? (value.ragStatus !== null && value.ragStatus !== 'completed' ? value.ragStatus : null);
    return {
        id: `knowledge-item:${String(value.id)}`,
        type: 'knowledgeItem',
        title: value.filename,
        status: statusParts.join(' - '),
        href: null,
        knowledgeAttachmentId,
        knowledgeItemId: value.id,
        documentId: value.documentId,
        unavailableReason,
        previewUrl: null,
        soaiPathContentPart: null,
        iconName: resolveFileEntryIconName({ name: value.filename, isDirectory: false })
    };
};

const parseKnowledgeItemsPage = (payload: KnowledgeAttachmentItemsResponse, knowledgeAttachmentId: string): KnowledgeItemsPage => {
    const items = payload.items.map((item) => parseKnowledgeItemRecord(item, knowledgeAttachmentId));
    return {
        items,
        nextCursor: parseKnowledgeCursor(payload.nextCursor)
    };
};

const buildKnowledgeItemsRequestOptions = (cursor: KnowledgeCursor | null, query: KnowledgeItemsQuery, signal: AbortSignal): KnowledgeItemsRequestOptions => {
    const options: KnowledgeItemsRequestOptions = {
        limit: KNOWLEDGE_PAGE_LIMIT,
        signal
    };
    if (cursor !== null) {
        options.cursorItemIndex = cursor.itemIndex;
        options.cursorId = cursor.id;
    }
    if (query.status !== null) {
        options.status = query.status;
    }
    if (query.query !== null) {
        options.query = query.query;
    }
    return options;
};

export { buildKnowledgeItemsRequestOptions, parseKnowledgeItemsPage };
export type { KnowledgeCursor, KnowledgeItemsPage, KnowledgeItemsQuery, KnowledgeItemsRequestOptions };
