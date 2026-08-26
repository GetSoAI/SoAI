/* SoAI - Chat feature attachments preview [frontend/assets/ts/features/chat/chatuimanager/attachmentsPreview.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isNonNegativeInteger, isString } from '@core/typeGuards.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedStringOrNull } from '@core/normalize.ts';
import { EMPTY_UI_HTML, uiAttr, uiHtml, uiText } from '@core/security/uiHtml.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { CHAT_ACTIONS } from '@features/chat/chatActionIds.ts';
import { CHAT_ATTACHMENT_INLINE_LIMIT, CHAT_ICON_SIZE_SM } from '@features/chat/chatConstants.ts';
import { appendPhysicalAttachmentProviderStatus } from '@features/chat/attachments/physicalAttachmentProviderStatus.ts';
import { reconcileAttachmentPreview, type AttachmentPreviewEntry } from '@features/chat/chatuimanager/attachmentPreviewReconciler.ts';
import { renderKnowledgeRows } from '@features/chat/chatuimanager/attachmentPreviewKnowledgeRows.ts';
import { getElement, setElementVisibility } from '@features/chat/chatuimanager/dom.ts';
import { buildChatFilePreviewItemDocumentMarkup } from '@features/chat/chatuimanager/filePreviewItemDocumentMarkup.ts';
import { isSoaiPathDraftRecord, requireSoaiPathDraftRecordVirtualPath, resolveSoaiPathDraftRecordMediaMetadata, resolveSoaiPathDraftRecordRootFingerprint } from '@features/chat/attachments/soaiPathDraftRecords.ts';
import { knowledgeSummaryMatchesIngestion } from '@features/chat/knowledgeAttachmentPresentation.ts';
import type { InlineMediaOpenAction } from '@features/chat/message/enhancers/inlineMultimediaCardTypes.ts';
import { renderChatMultimediaPreviewOpenActionAttributes, resolveChatMultimediaPreviewSourceReferenceForUrl } from '@features/chat/message/multimediaPreviewDataset.ts';
import type { ChatAttachment } from '@features/chat/ChatTypes.ts';
import type { ChatUIManagerContext } from '@features/chat/chatuimanager/types.ts';

const resolvePhysicalAttachmentMediaMetadata = (attachment: ChatAttachment): { contentType: string | null; contentLength: number | null } => {
    return {
        contentType: toTrimmedStringOrNull(attachment.mimeType),
        contentLength: isNonNegativeInteger(attachment.sizeBytes) ? attachment.sizeBytes : null
    };
};

const resolveImageAttachmentOpenAction = (context: ChatUIManagerContext, attachment: ChatAttachment, previewUrl: string): InlineMediaOpenAction => {
    const soaiPathRecord = attachment.soaiPathRecord;
    if (isSoaiPathDraftRecord(soaiPathRecord)) {
        const virtualPath = requireSoaiPathDraftRecordVirtualPath(soaiPathRecord);
        const conversationId = context.dependencies.session.getCurrentConversationId();
        const rootFingerprint = resolveSoaiPathDraftRecordRootFingerprint(soaiPathRecord);
        const metadata = resolveSoaiPathDraftRecordMediaMetadata(soaiPathRecord);
        return {
            type: 'image',
            previewUrl,
            openSourceUrl: previewUrl,
            title: attachment.name,
            downloadName: attachment.name,
            downloadUrl: null,
            contentType: metadata.contentType,
            contentLength: metadata.contentLength,
            sourceReference: conversationId === null || rootFingerprint === null ? null : { type: 'conversation_soai_path', conversationId, rootFingerprint, value: virtualPath },
            requireMetadata: false
        };
    }
    const metadata = resolvePhysicalAttachmentMediaMetadata(attachment);
    return {
        type: 'image',
        previewUrl,
        openSourceUrl: previewUrl,
        title: attachment.name,
        downloadName: attachment.name,
        downloadUrl: toTrimmedStringOrNull(attachment.downloadUrl),
        contentType: metadata.contentType,
        contentLength: metadata.contentLength,
        sourceReference: resolveChatMultimediaPreviewSourceReferenceForUrl(previewUrl),
        requireMetadata: false
    };
};

const renderImageAttachmentMedia = (context: ChatUIManagerContext, attachment: ChatAttachment, statusKey: ChatAttachment['parseStatus'], previewUrl: string | undefined): { markup: TrustedHtml; actionAttributes: TrustedHtml } => {
    if (isString(previewUrl) && previewUrl.trim()) {
        const srcValue = context.dependencies.sanitizer.image(previewUrl);
        if (srcValue) {
            const openAction = resolveImageAttachmentOpenAction(context, attachment, srcValue);
            const loadingOverlay = statusKey === 'processing' ? uiHtml`<span class="file-preview-image-loading" aria-hidden="true"><span class="loading-spinner file-preview-image-spinner" aria-hidden="true"></span></span>` : EMPTY_UI_HTML;
            return {
                markup: uiHtml`<img src="${uiAttr(srcValue)}" alt="${uiAttr(attachment.name)}" loading="lazy" decoding="async"/>${loadingOverlay}`,
                actionAttributes: renderChatMultimediaPreviewOpenActionAttributes(openAction)
            };
        }
    }
    const spinner = statusKey === 'processing' ? uiHtml`<span class="loading-spinner file-preview-image-spinner" aria-hidden="true"></span>` : EMPTY_UI_HTML;
    return {
        markup: uiHtml`<span class="file-preview-image-placeholder" aria-hidden="true">${spinner}</span>`,
        actionAttributes: EMPTY_UI_HTML
    };
};

const renderOverflowRow = (context: ChatUIManagerContext, hiddenCount: number): AttachmentPreviewEntry => {
    const labelText = i18n.plural('chat.attachments.overflowHidden', hiddenCount, { count: hiddenCount });
    const icon = context.dependencies.getCachedIcon('ellipsis', CHAT_ICON_SIZE_SM);
    return {
        id: 'attachment-overflow',
        html: uiHtml`<button type="button" class="file-preview-item document chat-attachment-summary-card chat-attachment-summary-card--overflow glass-surface-light glass-surface--bordered glass-surface--rounded" data-action="${uiAttr(CHAT_ACTIONS.OPEN_COMPOSER_ATTACHMENT_OVERFLOW)}" data-hidden-attachment-count="${uiAttr(hiddenCount)}" aria-label="${uiAttr(labelText)}" data-tooltip="${uiAttr(labelText)}"><span class="file-preview-leading-icon" aria-hidden="true">${icon}</span><span class="file-info"><span class="file-name">${uiText(labelText)}</span><span class="file-status"></span></span></button>`
    };
};

function updateAttachmentsPreview(context: ChatUIManagerContext): void {
    const preview = getElement(context, 'preview');
    if (!preview) {
        return;
    }
    context.dependencies.drafts.refreshDraftKnowledgeAttachments();

    const ingestion = context.dependencies.drafts.getRagIngestionStatus();
    const knowledgeRows = renderKnowledgeRows(context);
    const ingestionHasAuthoritativeRow = ingestion ? (context.dependencies.drafts.getDraftKnowledgeAttachments()?.some((summary) => knowledgeSummaryMatchesIngestion(summary, ingestion)) ?? false) : false;
    const showIngestion = Boolean(ingestion && (ingestion.state === 'running' || ingestion.state === 'paused' || ingestion.state === 'submitted') && !ingestionHasAuthoritativeRow);
    const hasKnowledgeRow = knowledgeRows.length > 0;

    const attachments = context.dependencies.drafts.getAttachments();
    const hasAttachments = isArray(attachments) && attachments.length > 0;
    if (!hasAttachments && !showIngestion && !hasKnowledgeRow) {
        reconcileAttachmentPreview(context, preview, []);
        setElementVisibility(context, 'preview', false);
        return;
    }

    const removeLabel = i18n.t('chat.attachments.removeTooltip');
    const removeAction = CHAT_ACTIONS.REMOVE_ATTACHED_FILE;
    const removeIcon = context.dependencies.getCachedIcon('close', { size: 12, strokeWidth: 2.2 });

    const attachmentRows: AttachmentPreviewEntry[] = [];
    for (const attachment of isArray(attachments) ? attachments : []) {
        if (!attachment) {
            continue;
        }
        if (!isString(attachment.name) || !attachment.name.trim()) {
            continue;
        }

        const statusKey = attachment.parseStatus;
        if (statusKey !== 'ready' && statusKey !== 'processing' && statusKey !== 'error') {
            continue;
        }

        const isSoaiPathLink = isSoaiPathDraftRecord(attachment.soaiPathRecord);

        if (attachment.isImage) {
            const media = renderImageAttachmentMedia(context, attachment, statusKey, attachment.previewUrl);
            const baseStatusLabel = statusKey === 'ready' ? i18n.t('chat.attachments.status.ready') : statusKey === 'processing' ? i18n.t('chat.attachments.status.processing') : i18n.t('chat.attachments.status.error');
            const providerStatusLabel = isSoaiPathLink ? baseStatusLabel : appendPhysicalAttachmentProviderStatus(attachment, baseStatusLabel);
            const statusMarkup = providerStatusLabel === baseStatusLabel ? EMPTY_UI_HTML : uiHtml`<span class="file-info"><span class="file-name">${uiText(attachment.name)}</span><span class="file-status">${uiText(providerStatusLabel)}</span></span>`;
            attachmentRows.push({
                id: `attachment:${attachment.id}`,
                html: uiHtml`<div class="file-preview-item image glass-surface-light glass-surface--bordered glass-surface--rounded"${media.actionAttributes} aria-label="${uiAttr(attachment.name)}">${media.markup}${statusMarkup}<button type="button" class="remove-file-btn" data-action="${uiAttr(removeAction)}" data-file-id="${uiAttr(attachment.id)}" aria-label="${uiAttr(removeLabel)}" data-tooltip="${uiAttr(removeLabel)}">${removeIcon}</button></div>`
            });
            continue;
        }

        const baseStatusLabel = isSoaiPathLink ? i18n.t('chat.attachments.status.soaiPathLink') : statusKey === 'ready' ? i18n.t('chat.attachments.status.ready') : statusKey === 'processing' ? i18n.t('chat.attachments.status.processing') : i18n.t('chat.attachments.status.error');
        const statusLabel = isSoaiPathLink ? baseStatusLabel : appendPhysicalAttachmentProviderStatus(attachment, baseStatusLabel);
        const removeButtonMarkup = uiHtml`<button type="button" class="remove-file-btn" data-action="${uiAttr(removeAction)}" data-file-id="${uiAttr(attachment.id)}" aria-label="${uiAttr(removeLabel)}" data-tooltip="${uiAttr(removeLabel)}">${removeIcon}</button>`;
        attachmentRows.push({
            id: `attachment:${attachment.id}`,
            html: buildChatFilePreviewItemDocumentMarkup({
                nameHtml: uiText(attachment.name),
                statusHtml: uiText(statusLabel),
                showSpinner: statusKey === 'processing',
                actionButtonMarkup: removeButtonMarkup,
                soaiPathLink: isSoaiPathLink
            })
        });
    }

    const ingestionRow =
        showIngestion && ingestion
            ? (() => {
                  const title = i18n.t('chat.ingestion.title');
                  const statusText =
                      ingestion.state === 'submitted'
                          ? i18n.t('chat.ingestion.filesSubmitted')
                          : ingestion.state === 'paused'
                            ? i18n.t('chat.ingestion.status.paused', {
                                  completed: ingestion.succeeded + ingestion.failed + ingestion.skipped,
                                  total: ingestion.total,
                                  queued: ingestion.queued,
                                  'in_flight': ingestion.inFlight,
                                  failed: ingestion.failed,
                                  skipped: ingestion.skipped
                              })
                            : i18n.t('chat.ingestion.status.running', {
                                  completed: ingestion.succeeded + ingestion.failed + ingestion.skipped,
                                  total: ingestion.total,
                                  queued: ingestion.queued,
                                  'in_flight': ingestion.inFlight,
                                  failed: ingestion.failed,
                                  skipped: ingestion.skipped
                              });
                  const cancelLabel = i18n.t('chat.ingestion.cancel');
                  const cancelAction = CHAT_ACTIONS.CANCEL_RAG_INGESTION;
                  const cancelIcon = context.dependencies.getCachedIcon('stop', CHAT_ICON_SIZE_SM);
                  const cancelButtonMarkup = uiHtml`<button type="button" class="remove-file-btn" data-action="${uiAttr(cancelAction)}" aria-label="${uiAttr(cancelLabel)}" data-tooltip="${uiAttr(cancelLabel)}">${cancelIcon}</button>`;
                  return {
                      id: ingestion.clientBatchId ? `knowledge-client:${ingestion.clientBatchId}` : `knowledge-ingestion:${context.dependencies.session.getCurrentConversationId() ?? 'active'}`,
                      html: buildChatFilePreviewItemDocumentMarkup({
                          nameHtml: uiText(title),
                          statusHtml: uiText(statusText),
                          showSpinner: ingestion.state === 'running' || ingestion.state === 'submitted',
                          actionButtonMarkup: cancelButtonMarkup
                      })
                  };
              })()
            : null;

    const allEntries = ingestionRow === null ? [...knowledgeRows, ...attachmentRows] : [ingestionRow, ...knowledgeRows, ...attachmentRows];
    const visibleEntries = allEntries.slice(0, CHAT_ATTACHMENT_INLINE_LIMIT);
    const hiddenCount = Math.max(0, allEntries.length - visibleEntries.length);
    const entries = hiddenCount > 0 ? [...visibleEntries, renderOverflowRow(context, hiddenCount)] : visibleEntries;
    if (entries.length === 0) {
        reconcileAttachmentPreview(context, preview, []);
        setElementVisibility(context, 'preview', false);
        return;
    }

    reconcileAttachmentPreview(context, preview, entries);
    setElementVisibility(context, 'preview', true);
}

export { updateAttachmentsPreview };
