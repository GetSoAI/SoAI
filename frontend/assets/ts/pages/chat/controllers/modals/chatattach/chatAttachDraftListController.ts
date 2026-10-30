/* SoAI - Chat draft snapshots for the reusable attachment list [frontend/assets/ts/pages/chat/controllers/modals/chatattach/chatAttachDraftListController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { securityApi } from '@core/security/public.ts';
import { AttachDraftListController, type AttachDraftListElements } from '@features/attachmodal/public.ts';
import { resolveChatAttachmentDraftSource, resolveDraftAttachmentIconName, resolvePhysicalAttachmentPreviewUrl, type ChatAttachment, type ChatAttachmentDraftSource } from '@features/chat/public.ts';
import type { ChatAttachDraftListHost } from '@pages/chat/controllers/modals/chatattach/contracts.ts';
import { createChatDraftPresentation } from '@pages/chat/controllers/modals/chatattach/chatAttachDraftPresentationController.ts';

const resolveChatAttachDraftListAttachments = (attachments: readonly ChatAttachment[], source: ChatAttachmentDraftSource): ChatAttachment[] => attachments.filter((attachment) => resolveChatAttachmentDraftSource(attachment) === source).reverse();

const createChatAttachDraftList = (host: ChatAttachDraftListHost, elements: AttachDraftListElements, signal: AbortSignal, source: ChatAttachmentDraftSource): AttachDraftListController =>
    new AttachDraftListController(
        {
            snapshot: () =>
                resolveChatAttachDraftListAttachments(host.attachments.drafts(), source).map((attachment) => {
                    const candidate = resolvePhysicalAttachmentPreviewUrl(host.conversation.currentId(), attachment);
                    return { attachment, iconName: resolveDraftAttachmentIconName(attachment), previewUrl: candidate === null ? null : securityApi.sanitizeImageSource(candidate) };
                }),
            subscribe: (handler) => host.attachments.subscribeDrafts(handler),
            remove: (id) => host.attachments.removeFile(id),
            run: (task) => host.execution.run('chat:attachModalDraftAttachmentRemove', task)
        },
        elements,
        signal,
        createChatDraftPresentation(elements, signal)
    );

export { createChatAttachDraftList, resolveChatAttachDraftListAttachments };
