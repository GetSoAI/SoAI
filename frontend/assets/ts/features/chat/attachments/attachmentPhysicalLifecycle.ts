/* SoAI - Chat physical attachment lifecycle operations [frontend/assets/ts/features/chat/attachments/attachmentPhysicalLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ModuleLogger } from '@core/moduleContext.ts';
import type { ConversationAttachmentChangedEvent } from '@core/realtime/eventcontracts/attachmentContracts.ts';
import { isString } from '@core/typeGuards.ts';
import type { ChatAttachment } from '@features/chat/ChatTypes.ts';
import { applyPhysicalAttachmentPayloadToChatAttachment } from '@features/chat/attachments/physicalAttachmentPayload.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

interface AttachmentLifecycleErrorHandler {
    (error: Error, title: string, options?: { notify?: boolean }): void;
}

interface ApplyPhysicalAttachmentChangedEventArguments {
    files: readonly ChatAttachment[];
    event: ConversationAttachmentChangedEvent;
    errorHandler: AttachmentLifecycleErrorHandler;
    syncUi: () => void;
}

interface DeleteStagedPhysicalAttachmentArguments {
    attachment: ChatAttachment;
    deletePhysicalAttachment: ((conversationId: string, attachmentId: string) => Promise<void>) | null;
    logger: ModuleLogger;
    errorHandler: AttachmentLifecycleErrorHandler;
}

const findPhysicalAttachment = (files: readonly ChatAttachment[], conversationId: string, attachmentId: string, clientAttachmentId: string): ChatAttachment | null => {
    for (const attachment of files) {
        if (!attachment) {
            continue;
        }
        const attachmentConversationId = normalizeConversationId(attachment.conversationId);
        if (attachmentConversationId && attachmentConversationId !== conversationId) {
            continue;
        }
        if (isString(attachment.attachmentId) && attachment.attachmentId.trim() === attachmentId) {
            return attachment;
        }
        if (isString(attachment.clientAttachmentId) && attachment.clientAttachmentId.trim() === clientAttachmentId) {
            return attachment;
        }
    }
    return null;
};

const notifyPhysicalAttachmentError = (attachment: ChatAttachment, errorHandler: AttachmentLifecycleErrorHandler): void => {
    const errorTitle = i18n.t('chat.upload.errorTitle');
    const parseError = isString(attachment.parseError) && attachment.parseError.trim() ? attachment.parseError.trim() : i18n.t('documents.errors.parseFailed');
    const message = i18n.t('chat.attachments.parseErrorNotification', {
        name: attachment.name,
        error: parseError
    });
    errorHandler(new Error(message), errorTitle, { notify: true });
};

const applyPhysicalAttachmentChangedEvent = (inputArguments: ApplyPhysicalAttachmentChangedEventArguments): void => {
    const parsed = inputArguments.event;
    const attachment = findPhysicalAttachment(inputArguments.files, parsed.convId, parsed.attachment.attachmentId, parsed.attachment.clientAttachmentId);
    if (!attachment) {
        return;
    }
    const priorStatus = attachment.parseStatus;
    const applied = applyPhysicalAttachmentPayloadToChatAttachment(attachment, parsed.convId, parsed.attachment);
    if (!applied) {
        return;
    }
    inputArguments.syncUi();
    if (priorStatus !== 'error' && attachment.parseStatus === 'error') {
        notifyPhysicalAttachmentError(attachment, inputArguments.errorHandler);
    }
};

const deleteStagedPhysicalAttachment = async (inputArguments: DeleteStagedPhysicalAttachmentArguments): Promise<void> => {
    if (inputArguments.attachment.state !== 'staged') {
        return;
    }
    const conversationId = normalizeConversationId(inputArguments.attachment.conversationId);
    const attachmentId = isString(inputArguments.attachment.attachmentId) ? inputArguments.attachment.attachmentId.trim() : '';
    if (!conversationId || !attachmentId || !inputArguments.deletePhysicalAttachment) {
        return;
    }
    const errorTitle = i18n.t('chat.upload.errorTitle');
    try {
        await inputArguments.deletePhysicalAttachment(conversationId, attachmentId);
    } catch (error) {
        const deleteError = ensureError(error);
        inputArguments.logger('error', 'Failed to delete staged chat attachment', deleteError);
        inputArguments.errorHandler(deleteError, errorTitle, { notify: true });
    }
};

export { applyPhysicalAttachmentChangedEvent, deleteStagedPhysicalAttachment };
export type { AttachmentLifecycleErrorHandler, ApplyPhysicalAttachmentChangedEventArguments, DeleteStagedPhysicalAttachmentArguments };
