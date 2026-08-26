/* SoAI - Chat send attachment payload revision controller [frontend/assets/ts/pages/chat/controllers/chatmessagesendingcontroller/chatAttachmentPayloadRevisionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { stableJsonStringify } from '@core/serialization/json.ts';
import type { ChatAttachment, ChatContentSegment } from '@features/chat/public.ts';

type PayloadAttachmentSnapshotEntry = {
    attachmentId: string;
    signature: string;
};

type PayloadAttachmentSnapshot = {
    entries: PayloadAttachmentSnapshotEntry[];
};

const resolveAttachmentPayloadEntrySignature = (attachment: ChatAttachment, contentPart: ChatContentSegment): string => {
    return stableJsonStringify([attachment.id, contentPart]);
};

const capturePayloadAttachmentSnapshot = (inputArguments: { attachments: readonly ChatAttachment[]; attachmentContent: readonly ChatContentSegment[] }): PayloadAttachmentSnapshot | null => {
    if (inputArguments.attachments.length !== inputArguments.attachmentContent.length) {
        return null;
    }
    const entries: PayloadAttachmentSnapshotEntry[] = [];
    for (let index = 0; index < inputArguments.attachments.length; index += 1) {
        const attachment = inputArguments.attachments[index];
        const contentPart = inputArguments.attachmentContent[index];
        if (!attachment || contentPart === undefined) {
            return null;
        }
        entries.push({
            attachmentId: attachment.id,
            signature: resolveAttachmentPayloadEntrySignature(attachment, contentPart)
        });
    }
    return { entries };
};

const matchesPayloadAttachmentSnapshot = (inputArguments: { currentAttachments: readonly ChatAttachment[]; currentAttachmentContent: readonly ChatContentSegment[]; capturedSnapshot: PayloadAttachmentSnapshot }): boolean => {
    const currentSnapshot = capturePayloadAttachmentSnapshot({
        attachments: inputArguments.currentAttachments,
        attachmentContent: inputArguments.currentAttachmentContent
    });
    if (currentSnapshot === null || currentSnapshot.entries.length !== inputArguments.capturedSnapshot.entries.length) {
        return false;
    }
    for (let index = 0; index < inputArguments.capturedSnapshot.entries.length; index += 1) {
        const currentEntry = currentSnapshot.entries[index];
        const capturedEntry = inputArguments.capturedSnapshot.entries[index];
        if (!currentEntry || !capturedEntry) {
            return false;
        }
        if (currentEntry.attachmentId !== capturedEntry.attachmentId || currentEntry.signature !== capturedEntry.signature) {
            return false;
        }
    }
    return true;
};

export { capturePayloadAttachmentSnapshot, matchesPayloadAttachmentSnapshot };
export type { PayloadAttachmentSnapshot };
