/* SoAI - Chat linked knowledge first item content preview [frontend/assets/ts/features/chat/message/knowledgeAttachmentFirstPreview.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { KnowledgeAttachmentSummary } from '@core/api/contracts/webuiAttachmentContracts.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import { createTextContentPreviewRequest } from '@core/ui/modals/contentpreview/requestFactories.ts';
import { requireContentPreviewModalService } from '@core/ui/modals/contentpreview/service.ts';
import { createLinkedKnowledgeClientBatchId } from '@features/chat/attachments/linkedKnowledgeClientBatchId.ts';
import { copyChatMessageTextWithFeedback } from '@features/chat/message/messageCopyNotifications.ts';
import { resolveKnowledgeAttachmentPreviewText, resolveKnowledgeAttachmentPreviewTitle } from '@features/chat/message/knowledgeAttachmentPreviewPayload.ts';
import type { ChatKnowledgeAttachmentsApi } from '@features/chat/pagecontracts/types.ts';
import { parseKnowledgeItemsPage } from '@features/chat/message/attachmentoverflowmodal/knowledgeItems.ts';

type KnowledgeAttachmentFirstPreviewArguments = {
    knowledgeAttachmentsApi: Pick<ChatKnowledgeAttachmentsApi, 'items' | 'previewItem' | 'useItems'>;
    targetConversationId: string;
    sourceConversationId: string;
    knowledgeAttachmentId: string;
    fallbackTitle: string;
    hasClipboardSupport: () => boolean;
    copyToClipboard: (text: string, options?: { notify?: (message: string, type: NotificationType) => void }) => Promise<void>;
    showNotification: (message: string, type: NotificationType) => void;
    onKnowledgeAttachmentChanged: (summary: KnowledgeAttachmentSummary) => void;
    shouldOpen?: (() => boolean) | undefined;
    shouldAttach?: (() => boolean) | undefined;
    signal?: AbortSignal | undefined;
};

const copyPreviewText = async (inputArguments: KnowledgeAttachmentFirstPreviewArguments, text: string): Promise<void> => {
    await copyChatMessageTextWithFeedback(
        {
            copyToClipboard: (value, options) => inputArguments.copyToClipboard(value, options),
            hasClipboardSupport: () => inputArguments.hasClipboardSupport(),
            showNotification: (message, type) => inputArguments.showNotification(message, type)
        },
        text
    );
};

const attachKnowledgeItem = async (inputArguments: KnowledgeAttachmentFirstPreviewArguments, itemId: number, documentId: string | null): Promise<void> => {
    if (inputArguments.signal?.aborted || inputArguments.shouldAttach?.() === false) {
        return;
    }
    const response = await inputArguments.knowledgeAttachmentsApi.useItems(
        inputArguments.targetConversationId,
        {
            sourceConvId: inputArguments.sourceConversationId,
            sourceKnowledgeAttachmentId: inputArguments.knowledgeAttachmentId,
            selections: [
                {
                    itemId: itemId,
                    documentId: documentId
                }
            ],
            clientBatchId: createLinkedKnowledgeClientBatchId({
                targetConversationId: inputArguments.targetConversationId,
                sourceConversationId: inputArguments.sourceConversationId,
                sourceKnowledgeAttachmentId: inputArguments.knowledgeAttachmentId,
                selections: [
                    {
                        itemId: itemId,
                        documentId: documentId
                    }
                ]
            })
        },
        { signal: inputArguments.signal }
    );
    if (inputArguments.signal?.aborted || inputArguments.shouldAttach?.() === false) {
        return;
    }
    inputArguments.onKnowledgeAttachmentChanged(response.summary);
    requireContentPreviewModalService().close();
};

const openKnowledgeAttachmentFirstPreview = async (inputArguments: KnowledgeAttachmentFirstPreviewArguments): Promise<void> => {
    const itemsPayload = await inputArguments.knowledgeAttachmentsApi.items(inputArguments.sourceConversationId, inputArguments.knowledgeAttachmentId, { limit: 1, status: 'completed', signal: inputArguments.signal });
    const item = parseKnowledgeItemsPage(itemsPayload, inputArguments.knowledgeAttachmentId).items[0];
    if (item === undefined || item.knowledgeItemId === null) {
        throw new Error('Linked knowledge attachment has no previewable items');
    }
    if (inputArguments.signal?.aborted || inputArguments.shouldOpen?.() === false) {
        return;
    }
    const itemId = item.knowledgeItemId;
    const previewPayload = await inputArguments.knowledgeAttachmentsApi.previewItem(inputArguments.sourceConversationId, inputArguments.knowledgeAttachmentId, String(itemId), { documentId: item.documentId }, { signal: inputArguments.signal });
    if (inputArguments.signal?.aborted || inputArguments.shouldOpen?.() === false) {
        return;
    }
    requireContentPreviewModalService().open(
        createTextContentPreviewRequest({
            scope: 'chat',
            type: 'text',
            headerDescription: i18n.t('chat.attachments.badge.knowledge'),
            baseline: {
                title: resolveKnowledgeAttachmentPreviewTitle(previewPayload, inputArguments.fallbackTitle),
                content: resolveKnowledgeAttachmentPreviewText(previewPayload),
                promptColor: null
            },
            editable: false,
            languageMode: 'default',
            disableCopyWhenEmpty: true,
            disableDownloadWhenEmpty: true,
            colorToolkit: null,
            onRequestSave: null,
            onRequestDownload: null,
            onRequestCopy: async (text) => await copyPreviewText(inputArguments, text),
            onRequestAttach: async () => await attachKnowledgeItem(inputArguments, itemId, item.documentId),
            enhance: null,
            openSourceUrl: null,
            onStatePotentiallyChanged: null,
            sourceReference: null,
            externalOpenBehavior: 'neverConfirm'
        })
    );
};

export { openKnowledgeAttachmentFirstPreview };
