/* SoAI - Chat attach modal draft attachment list state widget [frontend/assets/ts/features/attachmodal/draftState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { checkerboardService } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderInlineLoadingStatus } from '@core/ui/loadingStatus.ts';
import { reconcileDraftAttachmentListRows } from '@features/attachmodal/draftRows.ts';
import type { AttachDraftEntry, AttachDraftPresentation } from '@features/attachmodal/draftContracts.ts';
import type { AttachDraftListElements } from '@features/attachmodal/contracts.ts';

const setDraftAttachmentStatus = (elements: AttachDraftListElements, text: string, loading: boolean): void => {
    renderInlineLoadingStatus(elements.status, { text, loading });
};

const checkerboardLists = new WeakSet<HTMLElement>();

const renderDraftAttachmentListState = (elements: AttachDraftListElements, entries: readonly AttachDraftEntry[], processingCount: number, readyCount: number, presentation: AttachDraftPresentation): void => {
    const count = entries.length;
    const hasEntries = count > 0;
    setDraftAttachmentStatus(elements, processingCount > 0 ? i18n.plural('chat.attachModal.uploadProcessing', processingCount, { count: processingCount }) : '', processingCount > 0);
    elements.summary.textContent = readyCount > 0 ? i18n.plural('chat.attachModal.uploadSummary', readyCount, { count: readyCount }) : '';
    elements.summary.classList.toggle('u-hidden', readyCount === 0);
    elements.list.classList.toggle('u-hidden', !hasEntries);
    const reconciliation = reconcileDraftAttachmentListRows(elements.list, entries, presentation);
    if (!checkerboardLists.has(elements.list)) {
        checkerboardService.applyCheckerboard(elements.list, '.chat-attach-draft-attachment-row');
        checkerboardLists.add(elements.list);
    } else if (reconciliation.structureChanged) {
        checkerboardService.updateCheckerboard(elements.list, '.chat-attach-draft-attachment-row');
    }
    if (reconciliation.thumbnailsChanged) {
        presentation.prepareThumbnails(elements.list);
    }
};

export { renderDraftAttachmentListState };
