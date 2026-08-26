/* SoAI - Chat attachment overflow modal record counts [frontend/assets/ts/features/chat/message/attachmentoverflowmodal/counts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AttachmentOverflowRecord } from '@features/chat/message/attachmentoverflowmodal/records.ts';

type AttachmentOverflowRecordCounts = {
    all: number;
    attachment: number;
    soaiLink: number;
    knowledge: number;
};

const countAttachmentOverflowRecords = (records: readonly AttachmentOverflowRecord[]): AttachmentOverflowRecordCounts => {
    let attachment = 0;
    let soaiLink = 0;
    let knowledge = 0;
    for (const record of records) {
        if (record.type === 'attachment') {
            attachment += 1;
        } else if (record.type === 'soaiLink') {
            soaiLink += 1;
        } else if (record.type === 'knowledge' || record.type === 'knowledgeItem') {
            knowledge += 1;
        }
    }
    return {
        all: records.length,
        attachment,
        soaiLink,
        knowledge
    };
};

export { countAttachmentOverflowRecords };
export type { AttachmentOverflowRecordCounts };
