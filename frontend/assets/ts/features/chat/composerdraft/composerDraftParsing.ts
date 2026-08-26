/* SoAI - Chat composer draft response parsing [frontend/assets/ts/features/chat/composerdraft/composerDraftParsing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ConversationDraftResponse } from '@core/api/contracts/chatQueueDraftContracts.ts';
import { isPlainObject } from '@core/typeGuards.ts';
import { toJsonCompatibleObject } from '@core/primitives/clone.ts';
import { chatAttachmentFromPhysicalRecord } from '@features/chat/attachments/chatAttachmentFromPhysicalRecord.ts';
import { normalizeSoaiFileStoragePart } from '@features/chat/attachments/soaiFileContentPart.ts';
import { parseSoaiPathDraftRecord, serializeSoaiPathDraftRecord, type SoaiPathDraftRecord } from '@features/chat/attachments/soaiPathDraftRecords.ts';
import { buildProjectionSignature } from '@features/chat/composerdraft/composerDraftEntryProjection.ts';
import type { ParsedComposerDraft } from '@features/chat/composerdraft/composerDraftTypes.ts';

const emptyParsedComposerDraft = (revision = 0): ParsedComposerDraft => ({
    text: '',
    sourceText: '',
    attachmentContent: [],
    attachments: [],
    soaiPathRecords: [],
    signature: buildProjectionSignature('', '', []),
    revision
});

const parseComposerDraftResponse = (conversationId: string, response: ConversationDraftResponse): ParsedComposerDraft => {
    const draft = response.draft;
    if (draft === null) {
        return emptyParsedComposerDraft(response.revision);
    }
    const text = draft.text;
    const sourceText = draft.sourceText;
    const attachmentContent = draft.attachmentContent;
    const attachmentRows = draft.attachments;
    const soaiPathRecords: SoaiPathDraftRecord[] = [];
    const contentEntries: JsonValue[] = [];
    for (const entry of attachmentContent) {
        if (isPlainObject(entry) && entry['type'] === 'soai_path_record') {
            const record = parseSoaiPathDraftRecord(entry);
            soaiPathRecords.push(record);
            contentEntries.push(serializeSoaiPathDraftRecord(record));
            continue;
        }
        if (isPlainObject(entry)) {
            const normalizedFilePart = normalizeSoaiFileStoragePart(toJsonCompatibleObject(entry));
            if (normalizedFilePart !== null) {
                contentEntries.push(normalizedFilePart);
                continue;
            }
        }
        throw new Error('Conversation draft contains an invalid attachment entry.');
    }
    const attachments = attachmentRows.map((row) => chatAttachmentFromPhysicalRecord(conversationId, row));
    return {
        text,
        sourceText,
        attachmentContent: contentEntries,
        attachments,
        soaiPathRecords,
        signature: buildProjectionSignature(text, sourceText, contentEntries),
        revision: response.revision
    };
};

export { emptyParsedComposerDraft, parseComposerDraftResponse };
