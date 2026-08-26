/* SoAI - Chat attachment overflow modal filters [frontend/assets/ts/features/chat/message/attachmentoverflowmodal/filters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AttachmentOverflowRecord } from '@features/chat/message/attachmentoverflowmodal/records.ts';

type AttachmentOverflowCategoryFilter = 'all' | 'attachment' | 'soaiLink' | 'knowledge';
type KnowledgeStatusFilter = 'all' | 'queued' | 'fetching' | 'parsing' | 'chunking' | 'embedding' | 'completed' | 'error' | 'cancelled' | 'skipped';

const ATTACHMENT_OVERFLOW_CATEGORY_FILTERS: readonly AttachmentOverflowCategoryFilter[] = ['all', 'attachment', 'soaiLink', 'knowledge'];
const KNOWLEDGE_STATUS_FILTERS: readonly KnowledgeStatusFilter[] = ['all', 'queued', 'fetching', 'parsing', 'chunking', 'embedding', 'completed', 'error', 'cancelled', 'skipped'];
const ATTACHMENT_OVERFLOW_CATEGORY_FILTER_VALUES: ReadonlySet<string> = new Set(ATTACHMENT_OVERFLOW_CATEGORY_FILTERS);
const KNOWLEDGE_STATUS_FILTER_VALUES: ReadonlySet<string> = new Set(KNOWLEDGE_STATUS_FILTERS);

const isAttachmentOverflowCategoryFilter = (value: string): value is AttachmentOverflowCategoryFilter => ATTACHMENT_OVERFLOW_CATEGORY_FILTER_VALUES.has(value);
const isKnowledgeStatusFilter = (value: string): value is KnowledgeStatusFilter => KNOWLEDGE_STATUS_FILTER_VALUES.has(value);

const filterAttachmentOverflowRecords = (records: readonly AttachmentOverflowRecord[], filter: AttachmentOverflowCategoryFilter): AttachmentOverflowRecord[] => {
    if (filter === 'all') {
        return [...records];
    }
    if (filter === 'knowledge') {
        return records.filter((record) => record.type === 'knowledge' || record.type === 'knowledgeItem');
    }
    return records.filter((record) => record.type === filter);
};

export { ATTACHMENT_OVERFLOW_CATEGORY_FILTERS, KNOWLEDGE_STATUS_FILTERS, filterAttachmentOverflowRecords, isAttachmentOverflowCategoryFilter, isKnowledgeStatusFilter };
export type { AttachmentOverflowCategoryFilter, KnowledgeStatusFilter };
