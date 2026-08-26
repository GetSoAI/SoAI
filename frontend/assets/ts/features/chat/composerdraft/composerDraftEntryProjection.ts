/* SoAI - Chat composer draft projection [frontend/assets/ts/features/chat/composerdraft/composerDraftEntryProjection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { stableJsonStringify } from '@core/serialization/json.ts';
import { MAX_CHAT_COMPOSER_TEXT_LENGTH } from '@core/chat/protocols.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ChatAttachment } from '@features/chat/ChatTypes.ts';
import { buildSoaiFileContentPartFromAttachment, isSoaiFileAttachmentReadyForSend, serializeSoaiFileContentPart } from '@features/chat/attachments/soaiFileContentPart.ts';
import { isSoaiPathDraftRecord, serializeSoaiPathDraftRecord } from '@features/chat/attachments/soaiPathDraftRecords.ts';
import type { ComposerDraftProjection } from '@features/chat/composerdraft/composerDraftTypes.ts';

const projectDraftEntries = (attachments: readonly ChatAttachment[]): JsonValue[] => {
    const entries: JsonValue[] = [];
    for (const attachment of attachments) {
        if (isSoaiPathDraftRecord(attachment.soaiPathRecord)) {
            entries.push(serializeSoaiPathDraftRecord(attachment.soaiPathRecord));
            continue;
        }
        if (attachment.parseStatus === 'ready' && isSoaiFileAttachmentReadyForSend(attachment)) {
            entries.push(serializeSoaiFileContentPart(buildSoaiFileContentPartFromAttachment(attachment)));
        }
    }
    return entries;
};

const buildProjectionSignature = (text: string, sourceText: string, attachmentContent: readonly JsonValue[]): string => stableJsonStringify({ text, sourceText, attachmentContent: attachmentContent });

const isProjectionEmpty = (projection: ComposerDraftProjection): boolean => projection.text === '' && projection.attachmentContent.length === 0;

const projectComposerDraft = (inputArguments: { conversationId: string | null; text: string; sourceText: string; attachments: readonly ChatAttachment[] }): ComposerDraftProjection => {
    const attachmentContent = projectDraftEntries(inputArguments.attachments);
    return {
        conversationId: inputArguments.conversationId,
        text: inputArguments.text,
        sourceText: inputArguments.sourceText,
        attachmentContent,
        signature: buildProjectionSignature(inputArguments.text, inputArguments.sourceText, attachmentContent),
        textTooLong: inputArguments.text.length > MAX_CHAT_COMPOSER_TEXT_LENGTH || inputArguments.sourceText.length > MAX_CHAT_COMPOSER_TEXT_LENGTH
    };
};

export { buildProjectionSignature, isProjectionEmpty, projectComposerDraft };
