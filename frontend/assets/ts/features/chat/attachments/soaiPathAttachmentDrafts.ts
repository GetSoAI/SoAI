/* SoAI - Chat SoAI path draft attachment construction [frontend/assets/ts/features/chat/attachments/soaiPathAttachmentDrafts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { generateSecureId } from '@core/primitives/idGenerator.ts';
import type { ChatAttachment } from '@features/chat/ChatTypes.ts';
import { resolveSoaiPathDraftRecordPreviewType, resolveSoaiPathDraftRecordTitle, type SoaiPathDraftRecord } from '@features/chat/attachments/soaiPathDraftRecords.ts';

const SOAI_PATH_LINK_MIME_TYPE = 'application/x-soai-path-link';

const createSoaiPathAttachment = (record: SoaiPathDraftRecord): ChatAttachment => {
    return {
        id: generateSecureId({ prefix: 'soai-path-link', format: 'hex' }),
        file: null,
        name: resolveSoaiPathDraftRecordTitle(record),
        size: 0,
        type: SOAI_PATH_LINK_MIME_TYPE,
        isImage: resolveSoaiPathDraftRecordPreviewType(record) === 'image',
        parseStatus: 'ready',
        soaiPathRecord: record
    };
};

export { createSoaiPathAttachment };
