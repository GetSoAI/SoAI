/* SoAI - Chat attach modal draft attachment list state widget [frontend/assets/ts/pages/chat/controllers/modals/chatattach/chatAttachDraftAttachmentListStateWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { checkerboardService } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderInlineLoadingStatus } from '@core/ui/loadingStatus.ts';
import { createDraftAttachmentListRow } from '@pages/chat/controllers/modals/chatattach/chatAttachDraftAttachmentListRowsWidget.ts';
import type { ChatAttachDraftAttachmentListElements, ChatAttachDraftAttachmentListEntry } from '@pages/chat/controllers/modals/chatattach/types.ts';

const setDraftAttachmentStatus = (elements: ChatAttachDraftAttachmentListElements, text: string, loading: boolean): void => {
    renderInlineLoadingStatus(elements.status, { text, loading });
};

const renderDraftAttachmentListState = (elements: ChatAttachDraftAttachmentListElements, entries: readonly ChatAttachDraftAttachmentListEntry[], processingCount: number, readyCount: number): void => {
    const count = entries.length;
    const hasEntries = count > 0;
    setDraftAttachmentStatus(elements, processingCount > 0 ? i18n.plural('chat.attachModal.uploadProcessing', processingCount, { count: processingCount }) : '', processingCount > 0);
    elements.summary.textContent = readyCount > 0 ? i18n.plural('chat.attachModal.uploadSummary', readyCount, { count: readyCount }) : '';
    elements.summary.classList.toggle('u-hidden', readyCount === 0);
    elements.list.classList.toggle('u-hidden', !hasEntries);
    if (!hasEntries) {
        elements.list.replaceChildren();
        checkerboardService.applyCheckerboard(elements.list, '.chat-attach-draft-attachment-row');
        return;
    }
    const documentRef = elements.list.ownerDocument;
    elements.list.replaceChildren(...entries.map((entry) => createDraftAttachmentListRow(documentRef, entry.attachment)));
    checkerboardService.applyCheckerboard(elements.list, '.chat-attach-draft-attachment-row');
};

export { renderDraftAttachmentListState };
