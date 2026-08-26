/* SoAI - Chat composer in-memory draft cache [frontend/assets/ts/features/chat/composerdraft/composerDraftMemoryStore.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { emptyParsedComposerDraft } from '@features/chat/composerdraft/composerDraftParsing.ts';
import type { ComposerDraftProjection, ParsedComposerDraft } from '@features/chat/composerdraft/composerDraftTypes.ts';
import { isSoaiPathDraftRecord } from '@features/chat/attachments/soaiPathDraftRecords.ts';

class ComposerDraftMemoryStore {
    readonly #drafts = new Map<string, ParsedComposerDraft>();

    delete(conversationId: string): void {
        this.#drafts.delete(conversationId);
    }

    read(conversationId: string): ParsedComposerDraft {
        return this.#drafts.get(conversationId) ?? emptyParsedComposerDraft();
    }

    saveProjection(conversationId: string, projection: ComposerDraftProjection, attachments: ParsedComposerDraft['attachments']): void {
        const physicalAttachments = attachments.filter((attachment) => !isSoaiPathDraftRecord(attachment.soaiPathRecord));
        const soaiPathRecords = attachments.flatMap((attachment) => (isSoaiPathDraftRecord(attachment.soaiPathRecord) ? [attachment.soaiPathRecord] : []));
        this.#drafts.set(conversationId, {
            text: projection.text,
            sourceText: projection.sourceText,
            attachmentContent: projection.attachmentContent,
            attachments: physicalAttachments,
            soaiPathRecords,
            signature: projection.signature,
            revision: 0
        });
    }
}

export { ComposerDraftMemoryStore };
