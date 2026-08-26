/* SoAI - Chat feature attachment preview knowledge rows [frontend/assets/ts/features/chat/chatuimanager/attachmentPreviewKnowledgeRows.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { KnowledgeAttachmentSummary } from '@core/api/contracts/webuiAttachmentContracts.ts';
import { i18n } from '@core/i18n/index.ts';
import { uiAttr, uiHtml, uiText } from '@core/security/uiHtml.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { CHAT_ACTIONS } from '@features/chat/chatActionIds.ts';
import { buildChatFilePreviewItemDocumentMarkup } from '@features/chat/chatuimanager/filePreviewItemDocumentMarkup.ts';
import { completedKnowledgeItemCount } from '@features/chat/knowledgeAttachmentReadiness.ts';
import { resolveKnowledgeAttachmentPresentation, resolveKnowledgeAttachmentReconciliationId } from '@features/chat/knowledgeAttachmentPresentation.ts';
import type { AttachmentPreviewEntry } from '@features/chat/chatuimanager/attachmentPreviewReconciler.ts';
import type { ChatUIManagerContext } from '@features/chat/chatuimanager/types.ts';

const renderKnowledgeAttachmentRow = (context: ChatUIManagerContext, knowledge: KnowledgeAttachmentSummary): TrustedHtml => {
    const title = knowledge.title || i18n.t('chat.ingestion.title');
    const totalCount = knowledge.totalCount;
    const visibleCount = knowledge.visibleCount;
    const completedCount = completedKnowledgeItemCount(knowledge);
    const presentation = resolveKnowledgeAttachmentPresentation(knowledge);
    const statusText = `${presentation.label} - ${String(visibleCount)} / ${String(totalCount)}`;
    const knowledgeAttachmentId = knowledge.knowledgeAttachmentId;
    if (knowledgeAttachmentId) {
        const removeLabel = i18n.t('chat.attachments.removeTooltip');
        const removeIcon = context.dependencies.getCachedIcon('close', { size: 14, strokeWidth: 1.5 });
        const leadingMarkup = presentation.showSpinner ? uiHtml`<span class="loading-spinner" aria-hidden="true"></span>` : context.dependencies.getCachedIcon('file-database', { size: 16, strokeWidth: 1.5 });
        const bodyMarkup = completedCount > 0 ? uiHtml`<button type="button" class="chat-attachment-summary-card-body" data-action="${uiAttr(CHAT_ACTIONS.OPEN_KNOWLEDGE_ATTACHMENT_PREVIEW)}" data-knowledge-attachment-id="${uiAttr(knowledgeAttachmentId)}" data-knowledge-title="${uiAttr(title)}" aria-label="${uiAttr(title)}" data-tooltip="${uiAttr(title)}"><span class="file-preview-leading-icon" aria-hidden="true">${leadingMarkup}</span><span class="file-info"><span class="file-name">${uiText(title)}</span><span class="file-status">${uiText(statusText)}</span></span></button>` : uiHtml`<div class="chat-attachment-summary-card-body"><span class="file-preview-leading-icon" aria-hidden="true">${leadingMarkup}</span><span class="file-info"><span class="file-name">${uiText(title)}</span><span class="file-status">${uiText(statusText)}</span></span></div>`;
        return uiHtml`<div class="file-preview-item document chat-attachment-summary-card chat-attachment-summary-card--knowledge chat-attachment-summary-card--removable glass-surface-light glass-surface--bordered glass-surface--rounded">${bodyMarkup}<button type="button" class="ui-round-button ui-round-button--inline ui-round-button--delete chat-attachment-summary-card-delete" data-action="${uiAttr(CHAT_ACTIONS.REMOVE_DRAFT_KNOWLEDGE_ATTACHMENT)}" data-knowledge-attachment-id="${uiAttr(knowledgeAttachmentId)}" aria-label="${uiAttr(removeLabel)}" data-tooltip="${uiAttr(removeLabel)}">${removeIcon}</button></div>`;
    }
    return buildChatFilePreviewItemDocumentMarkup({
        nameHtml: uiText(title),
        statusHtml: uiText(statusText),
        showSpinner: presentation.showSpinner,
        actionButtonMarkup: uiHtml``
    });
};

const resolveKnowledgeAttachmentEntryId = (knowledge: KnowledgeAttachmentSummary, index: number): string => {
    if (knowledge.knowledgeAttachmentId || knowledge.clientBatchId) return resolveKnowledgeAttachmentReconciliationId(knowledge);
    return `knowledge:${String(index)}`;
};

const renderKnowledgeRows = (context: ChatUIManagerContext): AttachmentPreviewEntry[] => {
    const draftItems = context.dependencies.drafts.getDraftKnowledgeAttachments();
    if (draftItems !== null && draftItems.length > 0) {
        const entries: AttachmentPreviewEntry[] = [];
        for (let index = 0; index < draftItems.length; index += 1) {
            const item = draftItems[index];
            if (!item) {
                continue;
            }
            const html = renderKnowledgeAttachmentRow(context, item);
            if (html.html.trim().length > 0) {
                entries.push({ id: resolveKnowledgeAttachmentEntryId(item, index), html });
            }
        }
        return entries;
    }
    return [];
};

export { renderKnowledgeRows };
