/* SoAI - Chat feature attachments preview [frontend/assets/ts/features/chat/chatuimanager/attachmentsPreview.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildWebuiConversationAttachmentContentPath } from '@core/api/endpoints/webuiConversationPaths.ts';
import { serializeSoaiPathContentPart } from '@core/api/contracts/webuiSoaiPathSerialization.ts';
import { isArray, isNonNegativeInteger, isString } from '@core/typeGuards.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedStringOrNull } from '@core/normalize.ts';
import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { classifyFileBrowserMimeType } from '@core/fileexplorerbrowser/mediaClassification.ts';
import { stableJsonStringify } from '@core/serialization/json.ts';
import { EMPTY_UI_HTML, uiAttr, uiHtml, uiText } from '@core/security/uiHtml.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { CHAT_ACTIONS } from '@features/chat/chatActionIds.ts';
import { CHAT_ICON_SIZE_SM } from '@features/chat/chatConstants.ts';
import { resolvePhysicalAttachmentPreviewUrl } from '@features/chat/attachments/physicalAttachmentPreviewUrl.ts';
import { prepareAttachmentThumbnailLifecycles } from '@features/chat/attachments/chatImageLoadLifecycle.ts';
import { resolveDraftAttachmentIconName, resolveDraftAttachmentStatusLabel } from '@features/chat/attachments/draftAttachmentPresentation.ts';
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
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';

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

const renderLeadingIcon = (context: ChatUIManagerContext, iconName: IconName): TrustedHtml => uiHtml`<span class="file-preview-leading-icon" aria-hidden="true">${context.dependencies.getCachedIcon(iconName, { size: 16, strokeWidth: 1.5 })}</span>`;

const resolveDraftAttachmentOpenAttributes = (context: ChatUIManagerContext, attachment: ChatAttachment, imageActionAttributes: TrustedHtml): TrustedHtml | undefined => {
    const record = attachment.soaiPathRecord;
    if (isSoaiPathDraftRecord(record)) {
        const serializedContentPart = stableJsonStringify(serializeSoaiPathContentPart(record.contentPart));
        return uiHtml` data-action="${uiAttr(CHAT_ACTIONS.OPEN_SOAI_PATH_PREVIEW)}" data-soai-path-title="${uiAttr(attachment.name)}" data-soai-path-content-part="${uiAttr(serializedContentPart)}"`;
    }
    const conversationId = toTrimmedStringOrNull(attachment.conversationId) ?? toTrimmedStringOrNull(context.dependencies.session.getCurrentConversationId());
    const attachmentId = toTrimmedStringOrNull(attachment.attachmentId);
    const contentType = toTrimmedStringOrNull(attachment.mimeType) ?? toTrimmedStringOrNull(attachment.type) ?? '';
    const previewType = toTrimmedStringOrNull(attachment.previewType) ?? classifyFileBrowserMimeType(contentType);
    if (conversationId !== null && attachmentId !== null && previewType !== null) {
        const previewUrl = buildWebuiConversationAttachmentContentPath(conversationId, attachmentId, false);
        const downloadUrl = buildWebuiConversationAttachmentContentPath(conversationId, attachmentId, true);
        const contentLength = isNonNegativeInteger(attachment.sizeBytes) ? attachment.sizeBytes : isNonNegativeInteger(attachment.size) ? attachment.size : 0;
        return uiHtml` data-action="${uiAttr(CHAT_ACTIONS.OPEN_SOAI_FILE_PREVIEW)}" data-soai-file-conversation-id="${uiAttr(conversationId)}" data-soai-file-preview-type="${uiAttr(previewType)}" data-soai-file-preview-url="${uiAttr(previewUrl)}" data-soai-file-download-url="${uiAttr(downloadUrl)}" data-soai-file-title="${uiAttr(attachment.name)}" data-soai-file-content-type="${uiAttr(contentType)}" data-soai-file-content-length="${uiAttr(contentLength)}"`;
    }
    return imageActionAttributes.html.length > 0 ? imageActionAttributes : undefined;
};

const renderImageAttachmentMedia = (context: ChatUIManagerContext, attachment: ChatAttachment, statusKey: ChatAttachment['parseStatus'], previewUrl: string | null, iconName: IconName): { markup: TrustedHtml; actionAttributes: TrustedHtml } => {
    const icon = context.dependencies.getCachedIcon(iconName, { size: 20, strokeWidth: 1.5 });
    const loadingOverlay = statusKey === 'processing' ? uiHtml`<span class="file-preview-image-loading" aria-hidden="true"><span class="loading-spinner file-preview-image-spinner" aria-hidden="true"></span></span>` : EMPTY_UI_HTML;
    if (previewUrl !== null) {
        const srcValue = context.dependencies.sanitizer.image(previewUrl);
        if (srcValue) {
            const openAction = resolveImageAttachmentOpenAction(context, attachment, srcValue);
            return {
                markup: uiHtml`<span class="chat-attachment-visual" data-attachment-image-state="loading"><span class="file-preview-leading-icon" aria-hidden="true">${icon}</span><img src="${uiAttr(srcValue)}" alt="${uiAttr(attachment.name)}" loading="lazy" decoding="async" data-chat-attachment-thumbnail="true"/>${loadingOverlay}</span>`,
                actionAttributes: renderChatMultimediaPreviewOpenActionAttributes(openAction)
            };
        }
    }
    return {
        markup: uiHtml`<span class="chat-attachment-visual" data-attachment-image-state="error"><span class="file-preview-leading-icon" aria-hidden="true">${icon}</span>${loadingOverlay}</span>`,
        actionAttributes: EMPTY_UI_HTML
    };
};

const renderOverflowRow = (context: ChatUIManagerContext, hiddenCount: number): AttachmentPreviewEntry => {
    const labelText = i18n.plural('chat.attachments.overflowHidden', hiddenCount, { count: hiddenCount });
    const showMoreLabel = i18n.t('chat.attachments.showMore');
    const icon = context.dependencies.getCachedIcon('ellipsis', CHAT_ICON_SIZE_SM);
    return {
        id: 'attachment-overflow',
        html: uiHtml`<button type="button" class="file-preview-item document chat-attachment-summary-card--overflow glass-surface-light glass-surface--bordered glass-surface--rounded" data-action="${uiAttr(CHAT_ACTIONS.OPEN_ATTACH_MODAL)}" data-hidden-attachment-count="${uiAttr(hiddenCount)}" aria-label="${uiAttr(labelText)}" data-tooltip="${uiAttr(labelText)}"><span class="file-preview-leading-icon" aria-hidden="true">${icon}</span><span class="file-info"><span class="file-name">${uiText(labelText)}</span><span class="file-status">${uiText(showMoreLabel)}</span></span></button>`
    };
};

const previewEntriesFitOneRow = (preview: HTMLElement): boolean => {
    const elements = Array.from(preview.children).filter((child): child is HTMLElement => child instanceof HTMLElement);
    const first = elements[0];
    if (first === undefined) {
        return true;
    }
    const firstTop = measureLayoutBox(first).top;
    return elements.every((element) => Math.abs(measureLayoutBox(element).top - firstTop) <= 1);
};

const reconcileResponsiveAttachmentPreview = (context: ChatUIManagerContext, preview: HTMLElement, allEntries: readonly AttachmentPreviewEntry[]): void => {
    let visibleCount = allEntries.length;
    let thumbnailsChanged = false;
    while (visibleCount >= 0) {
        const hiddenCount = allEntries.length - visibleCount;
        const visibleEntries = allEntries.slice(0, visibleCount);
        const entries = hiddenCount > 0 ? [...visibleEntries, renderOverflowRow(context, hiddenCount)] : visibleEntries;
        thumbnailsChanged = reconcileAttachmentPreview(context, preview, entries).thumbnailsChanged || thumbnailsChanged;
        if (previewEntriesFitOneRow(preview) || visibleCount === 0) {
            break;
        }
        visibleCount -= 1;
    }

    if (thumbnailsChanged) {
        prepareAttachmentThumbnailLifecycles(preview);
    }
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
    const previewAttachments = isArray(attachments) ? [...attachments].reverse() : [];
    for (const attachment of previewAttachments) {
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
        const iconName = resolveDraftAttachmentIconName(attachment);

        if (attachment.isImage) {
            const media = renderImageAttachmentMedia(context, attachment, statusKey, resolvePhysicalAttachmentPreviewUrl(context.dependencies.session.getCurrentConversationId(), attachment), iconName);
            const baseStatusLabel = resolveDraftAttachmentStatusLabel(statusKey);
            const statusLabel = isSoaiPathLink ? baseStatusLabel : appendPhysicalAttachmentProviderStatus(attachment, baseStatusLabel);
            const removeButtonMarkup = uiHtml`<button type="button" class="remove-file-btn" data-action="${uiAttr(removeAction)}" data-file-id="${uiAttr(attachment.id)}" aria-label="${uiAttr(removeLabel)}" data-tooltip="${uiAttr(removeLabel)}">${removeIcon}</button>`;
            attachmentRows.push({
                id: `attachment:${attachment.id}`,
                html: buildChatFilePreviewItemDocumentMarkup({
                    leadingVisualMarkup: media.markup,
                    interactiveBodyAttributesMarkup: resolveDraftAttachmentOpenAttributes(context, attachment, media.actionAttributes),
                    interactiveBodyLabel: attachment.name,
                    nameHtml: uiText(attachment.name),
                    statusHtml: uiText(statusLabel),
                    showSpinner: false,
                    actionButtonMarkup: removeButtonMarkup,
                    soaiPathLink: isSoaiPathLink
                })
            });
            continue;
        }

        const baseStatusLabel = isSoaiPathLink ? i18n.t('chat.attachments.status.soaiPathLink') : statusKey === 'ready' ? i18n.t('chat.attachments.status.ready') : statusKey === 'processing' ? i18n.t('chat.attachments.status.processing') : i18n.t('chat.attachments.status.error');
        const statusLabel = isSoaiPathLink ? baseStatusLabel : appendPhysicalAttachmentProviderStatus(attachment, baseStatusLabel);
        const removeButtonMarkup = uiHtml`<button type="button" class="remove-file-btn" data-action="${uiAttr(removeAction)}" data-file-id="${uiAttr(attachment.id)}" aria-label="${uiAttr(removeLabel)}" data-tooltip="${uiAttr(removeLabel)}">${removeIcon}</button>`;
        attachmentRows.push({
            id: `attachment:${attachment.id}`,
            html: buildChatFilePreviewItemDocumentMarkup({
                leadingVisualMarkup: renderLeadingIcon(context, iconName),
                interactiveBodyAttributesMarkup: resolveDraftAttachmentOpenAttributes(context, attachment, EMPTY_UI_HTML),
                interactiveBodyLabel: attachment.name,
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
                          leadingVisualMarkup: renderLeadingIcon(context, 'file-database'),
                          nameHtml: uiText(title),
                          statusHtml: uiText(statusText),
                          showSpinner: ingestion.state === 'running' || ingestion.state === 'submitted',
                          actionButtonMarkup: cancelButtonMarkup
                      })
                  };
              })()
            : null;

    const allEntries = ingestionRow === null ? [...attachmentRows, ...knowledgeRows] : [...attachmentRows, ingestionRow, ...knowledgeRows];
    if (allEntries.length === 0) {
        reconcileAttachmentPreview(context, preview, []);
        setElementVisibility(context, 'preview', false);
        return;
    }

    setElementVisibility(context, 'preview', true);
    reconcileResponsiveAttachmentPreview(context, preview, allEntries);
}

export { updateAttachmentsPreview };
