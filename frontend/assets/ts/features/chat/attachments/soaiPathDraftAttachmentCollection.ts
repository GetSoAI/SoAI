/* SoAI - SoAI path draft attachment collection [frontend/assets/ts/features/chat/attachments/soaiPathDraftAttachmentCollection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatAttachment, ChatAttachmentDraftSource } from '@features/chat/ChatTypes.ts';
import { createSoaiPathAttachment } from '@features/chat/attachments/soaiPathAttachmentDrafts.ts';
import { isSoaiPathDraftRecord, type SoaiPathDraftRecord } from '@features/chat/attachments/soaiPathDraftRecords.ts';
import type { SoaiPathImagePreviewLifecycle } from '@features/chat/attachments/soaiPathImagePreviewLifecycle.ts';

interface SoaiPathDraftAttachmentCollection {
    attachments: ChatAttachment[];
    imagePreviewLifecycle: SoaiPathImagePreviewLifecycle;
    isAttachmentPresent: (attachmentId: string) => boolean;
    syncUi: () => void;
}

interface SoaiPathDraftAttachmentDiscardResult {
    attachments: ChatAttachment[];
    removed: ChatAttachment[];
}

const loadSoaiPathAttachmentPreview = (collection: SoaiPathDraftAttachmentCollection, attachment: ChatAttachment): void => {
    collection.imagePreviewLifecycle.load(attachment, collection.isAttachmentPresent, collection.syncUi);
};

const addResolvedSoaiPathAttachments = (collection: SoaiPathDraftAttachmentCollection, records: readonly SoaiPathDraftRecord[], draftSource: Extract<ChatAttachmentDraftSource, 'browse' | 'soaiLink'>): number => {
    if (records.length === 0) {
        return 0;
    }
    let addedCount = 0;
    for (const record of records) {
        const attachment = createSoaiPathAttachment(record, draftSource);
        collection.attachments.push(attachment);
        loadSoaiPathAttachmentPreview(collection, attachment);
        addedCount += 1;
    }
    return addedCount;
};

const loadSoaiPathAttachmentPreviews = (collection: SoaiPathDraftAttachmentCollection): void => {
    for (const attachment of collection.attachments) {
        loadSoaiPathAttachmentPreview(collection, attachment);
    }
};

const discardSoaiPathDraftAttachments = (attachments: readonly ChatAttachment[], imagePreviewLifecycle: SoaiPathImagePreviewLifecycle, deleteAttachment: (attachmentId: string) => void): SoaiPathDraftAttachmentDiscardResult => {
    const removed = attachments.filter((attachment) => isSoaiPathDraftRecord(attachment.soaiPathRecord));
    if (removed.length === 0) {
        return { attachments: [...attachments], removed: [] };
    }
    const removedIds = new Set(removed.map((attachment) => attachment.id));
    const retained = attachments.filter((attachment) => !removedIds.has(attachment.id));
    imagePreviewLifecycle.releaseAll(removed);
    for (const attachment of removed) {
        deleteAttachment(attachment.id);
    }
    return { attachments: retained, removed };
};

export { addResolvedSoaiPathAttachments, discardSoaiPathDraftAttachments, loadSoaiPathAttachmentPreviews };
