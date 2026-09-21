/* SoAI - Sent chat attachment summary card rendering [frontend/assets/ts/features/chat/message/messageview/attachmentSummaryCards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildWebuiConversationAttachmentContentPath, buildWebuiConversationAttachmentThumbnailPath, buildWebuiConversationSoaiPathContentPath, buildWebuiConversationSoaiPathThumbnailPath } from '@core/api/endpoints/webuiConversationPaths.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatBytes } from '@core/primitives/byteSize.ts';
import { stableJsonStringify } from '@core/serialization/json.ts';
import { serializeSoaiPathContentPart } from '@core/api/contracts/webuiSoaiPathSerialization.ts';
import { getBadgeColorClass } from '@core/ui/badgeColors.ts';
import { resolveFileEntryIconName } from '@core/fileexplorerbrowser/entryIconResolution.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { CHAT_ACTIONS } from '@features/chat/chatActionIds.ts';
import { CHAT_ATTACHMENT_INLINE_LIMIT } from '@features/chat/chatConstants.ts';
import { renderChatMultimediaPreviewOpenActionAttributes, resolveChatMultimediaPreviewSourceReferenceForUrl } from '@features/chat/message/multimediaPreviewDataset.ts';
import type { ChatMessageRenderHost, ImageSegment, MessageRenderOptions, MessageSegment, SoaiFileSegment, SoaiFileUnavailableSegment, SoaiKnowledgeSegment, SoaiKnowledgeUnavailableSegment, SoaiPathSegment } from '@features/chat/message/messageview/types.ts';

type AttachmentSummarySegment = ImageSegment | SoaiFileSegment | SoaiKnowledgeSegment | SoaiPathSegment | SoaiFileUnavailableSegment | SoaiKnowledgeUnavailableSegment;

const isAttachmentSummarySegment = (segment: MessageSegment): segment is AttachmentSummarySegment => {
    return segment.type === 'image' || segment.type === 'soai_file' || segment.type === 'soai_knowledge' || segment.type === 'soai_path' || segment.type === 'soai_file_unavailable' || segment.type === 'soai_knowledge_unavailable';
};

const requireConversationId = (options: MessageRenderOptions): string => {
    const conversationId = options.conversationId;
    if (typeof conversationId !== 'string' || !conversationId.trim()) {
        throw new Error('Sent attachment cards require a conversation id');
    }
    return conversationId.trim();
};

const renderBadge = (host: ChatMessageRenderHost, label: string): string => {
    const colorClass = host.escapeAttribute(getBadgeColorClass(`chat-attachment:${label}`));
    return `<span class="chat-attachment-badge ui-model-type-badge ui-badge--micro ${colorClass}">${host.escapeHtml(label)}</span>`;
};

const renderDocumentCardBody = (host: ChatMessageRenderHost, iconName: IconName, title: string, status: string, badge: string): string => {
    const icon = host.getIconHtml(iconName, { size: 16, strokeWidth: 1.5 });
    return `<span class="file-preview-leading-icon" aria-hidden="true">${icon}</span><span class="file-info"><span class="file-name">${host.escapeHtml(title)}</span><span class="file-status">${badge}<span>${host.escapeHtml(status)}</span></span></span>`;
};

type ImageSummaryCardArguments = {
    className: string;
    thumbnailUrl: string;
    previewUrl: string;
    openSourceUrl: string;
    title: string;
    status: string;
    badge: string;
    label: string;
    downloadName: string;
    downloadUrl: string | null;
    contentType: string | null;
    contentLength: number | null;
    sourceReference: ReturnType<typeof resolveChatMultimediaPreviewSourceReferenceForUrl> | { type: 'path'; value: string } | null;
    attributes: string;
    iconName: IconName;
};

const renderImageSummaryCard = (host: ChatMessageRenderHost, inputArguments: ImageSummaryCardArguments): string => {
    const thumbnailSrc = host.sanitizeImage(inputArguments.thumbnailUrl);
    const actionAttributes = renderChatMultimediaPreviewOpenActionAttributes({
        type: 'image',
        previewUrl: inputArguments.previewUrl,
        openSourceUrl: inputArguments.openSourceUrl,
        title: inputArguments.title,
        downloadName: inputArguments.downloadName,
        downloadUrl: inputArguments.downloadUrl,
        contentType: inputArguments.contentType,
        contentLength: inputArguments.contentLength,
        sourceReference: inputArguments.sourceReference,
        requireMetadata: false
    });
    const status = `<span>${host.escapeHtml(inputArguments.status)}</span>`;
    const icon = host.getIconHtml(inputArguments.iconName, { size: 20, strokeWidth: 1.5 });
    const image = thumbnailSrc === null ? '' : `<img src="${host.escapeAttribute(thumbnailSrc)}" alt="${host.escapeAttribute(inputArguments.title)}" loading="lazy" decoding="async" data-chat-attachment-thumbnail="true">`;
    const state = thumbnailSrc === null ? 'error' : 'loading';
    return `<button type="button" class="file-preview-item document chat-attachment-summary-card ${host.escapeAttribute(inputArguments.className)} glass-surface-light glass-surface--bordered glass-surface--rounded"${inputArguments.attributes}${actionAttributes.html} aria-label="${host.escapeAttribute(inputArguments.label)}" data-tooltip="${host.escapeAttribute(inputArguments.label)}"><span class="chat-attachment-visual" data-attachment-image-state="${state}"><span class="file-preview-leading-icon" aria-hidden="true">${icon}</span>${image}</span><span class="file-info"><span class="file-name">${host.escapeHtml(inputArguments.title)}</span><span class="file-status">${inputArguments.badge}${status}</span></span></button>`;
};

const renderDocumentActionCard = (host: ChatMessageRenderHost, inputArguments: { className: string; iconName: IconName; title: string; status: string; badge: string; label: string; actionAttributes: string; extraAttributes?: string }): string => {
    const body = renderDocumentCardBody(host, inputArguments.iconName, inputArguments.title, inputArguments.status, inputArguments.badge);
    return `<button type="button" class="file-preview-item document chat-attachment-summary-card ${host.escapeAttribute(inputArguments.className)} glass-surface-light glass-surface--bordered glass-surface--rounded"${inputArguments.actionAttributes}${inputArguments.extraAttributes ?? ''} aria-label="${host.escapeAttribute(inputArguments.label)}" data-tooltip="${host.escapeAttribute(inputArguments.label)}">${body}</button>`;
};

const renderDocumentStaticCard = (host: ChatMessageRenderHost, inputArguments: { className: string; iconName: IconName; title: string; status: string; badge: string; label: string }): string => {
    const body = renderDocumentCardBody(host, inputArguments.iconName, inputArguments.title, inputArguments.status, inputArguments.badge);
    return `<div class="file-preview-item document chat-attachment-summary-card ${host.escapeAttribute(inputArguments.className)} glass-surface-light glass-surface--bordered glass-surface--rounded" aria-label="${host.escapeAttribute(inputArguments.label)}" data-tooltip="${host.escapeAttribute(inputArguments.label)}">${body}</div>`;
};

const renderSoaiFileCard = (host: ChatMessageRenderHost, segment: SoaiFileSegment, options: MessageRenderOptions): string => {
    const conversationId = requireConversationId(options);
    const thumbnailUrl = buildWebuiConversationAttachmentThumbnailPath(conversationId, segment.attachmentId);
    const previewUrl = buildWebuiConversationAttachmentContentPath(conversationId, segment.attachmentId, false);
    const downloadUrl = buildWebuiConversationAttachmentContentPath(conversationId, segment.attachmentId, true);
    const badge = renderBadge(host, i18n.t('chat.attachments.badge.attachment'));
    const status = `${segment.mimeType} - ${formatBytes(segment.sizeBytes, 1)}`;
    const attachmentId = host.escapeAttribute(segment.attachmentId);
    const fileId = host.escapeAttribute(segment.fileId);
    const iconName = resolveFileEntryIconName({ name: segment.filename, mimeType: segment.mimeType, isDirectory: false });
    if (segment.previewType === 'image') {
        return renderImageSummaryCard(host, {
            className: 'chat-attachment-summary-card--attachment',
            thumbnailUrl,
            previewUrl,
            openSourceUrl: downloadUrl,
            title: segment.filename,
            status,
            badge,
            label: i18n.t('chat.attachments.openAttachment'),
            downloadName: segment.filename,
            downloadUrl,
            contentType: segment.mimeType,
            contentLength: segment.sizeBytes,
            sourceReference: resolveChatMultimediaPreviewSourceReferenceForUrl(previewUrl),
            attributes: ` data-soai-attachment-id="${attachmentId}" data-soai-file-id="${fileId}"`,
            iconName
        });
    }
    const actionAttributes = ` data-action="${host.escapeAttribute(CHAT_ACTIONS.OPEN_SOAI_FILE_PREVIEW)}" data-soai-file-conversation-id="${host.escapeAttribute(conversationId)}" data-soai-file-preview-type="${host.escapeAttribute(segment.previewType)}" data-soai-file-preview-url="${host.escapeAttribute(previewUrl)}" data-soai-file-download-url="${host.escapeAttribute(downloadUrl)}" data-soai-file-title="${host.escapeAttribute(segment.filename)}" data-soai-file-content-type="${host.escapeAttribute(segment.mimeType)}" data-soai-file-content-length="${host.escapeAttribute(String(segment.sizeBytes))}"`;
    return renderDocumentActionCard(host, {
        className: 'chat-attachment-summary-card--attachment',
        iconName,
        title: segment.filename,
        status,
        badge,
        label: i18n.t('chat.attachments.openAttachment'),
        actionAttributes,
        extraAttributes: ` data-soai-attachment-id="${attachmentId}" data-soai-file-id="${fileId}"`
    });
};

const renderImageAttachmentCard = (host: ChatMessageRenderHost, segment: ImageSegment): string => {
    const previewUrl = segment.imageUrl;
    const title = segment.title || i18n.t('chat.message.generatedImage');
    const badge = renderBadge(host, i18n.t('chat.attachments.badge.attachment'));
    return renderImageSummaryCard(host, {
        className: 'chat-attachment-summary-card--attachment',
        thumbnailUrl: previewUrl,
        previewUrl,
        openSourceUrl: previewUrl,
        title,
        status: i18n.t('chat.inlinePreviews.typeLabel.image'),
        badge,
        label: i18n.t('chat.attachments.openAttachment'),
        downloadName: title,
        downloadUrl: previewUrl,
        contentType: null,
        contentLength: null,
        sourceReference: resolveChatMultimediaPreviewSourceReferenceForUrl(previewUrl),
        attributes: '',
        iconName: resolveFileEntryIconName({ name: title, isDirectory: false, mimeType: 'image/*' })
    });
};

const renderSoaiPathCard = (host: ChatMessageRenderHost, segment: SoaiPathSegment, options: MessageRenderOptions): string => {
    const badge = renderBadge(host, i18n.t('chat.attachments.badge.soaiLink'));
    const label = i18n.t('chat.attachments.openSoaiLink');
    const iconName = resolveFileEntryIconName({ name: segment.title, mimeType: segment.mimeType ?? segment.contentPart.mimeType, isDirectory: segment.entryType === 'folder' });
    const status = segment.entryType === 'folder' ? segment.virtualPath : `${segment.entryType}${segment.sizeBytes === undefined ? '' : ` - ${formatBytes(segment.sizeBytes, 1)}`}`;
    const serializedContentPart = stableJsonStringify(serializeSoaiPathContentPart(segment.contentPart));
    const actionAttributes = ` data-action="${host.escapeAttribute(CHAT_ACTIONS.OPEN_SOAI_PATH_PREVIEW)}" data-soai-path-title="${host.escapeAttribute(segment.title)}" data-soai-path-content-part="${host.escapeAttribute(serializedContentPart)}"`;
    const metadataAttributes = ` data-soai-path-title="${host.escapeAttribute(segment.title)}" data-soai-path-content-part="${host.escapeAttribute(serializedContentPart)}"`;
    if (segment.entryType === 'file' && segment.previewType === 'image') {
        const conversationId = requireConversationId(options);
        const thumbnailUrl = buildWebuiConversationSoaiPathThumbnailPath(conversationId, segment.contentPart);
        const previewUrl = buildWebuiConversationSoaiPathContentPath(conversationId, segment.contentPart, false);
        const downloadUrl = buildWebuiConversationSoaiPathContentPath(conversationId, segment.contentPart, true);
        return renderImageSummaryCard(host, {
            className: 'chat-attachment-summary-card--soai-link',
            thumbnailUrl,
            previewUrl,
            openSourceUrl: previewUrl,
            title: segment.title,
            status,
            badge,
            label,
            downloadName: segment.title,
            downloadUrl,
            contentType: segment.mimeType ?? null,
            contentLength: segment.sizeBytes ?? null,
            sourceReference: {
                type: 'conversation_soai_path',
                conversationId,
                rootFingerprint: segment.rootFingerprint,
                value: segment.virtualPath
            },
            attributes: metadataAttributes,
            iconName
        });
    }
    return renderDocumentActionCard(host, {
        className: 'chat-attachment-summary-card--soai-link',
        iconName,
        title: segment.title,
        status,
        badge,
        label,
        actionAttributes
    });
};

const renderSoaiKnowledgeCard = (host: ChatMessageRenderHost, segment: SoaiKnowledgeSegment): string => {
    const badge = renderBadge(host, i18n.t('chat.attachments.badge.knowledge'));
    const status = `${String(segment.visibleCount)} / ${String(segment.totalCount)}`;
    if (segment.sourceType === 'linked_knowledge') {
        return renderDocumentStaticCard(host, {
            className: 'chat-attachment-summary-card--knowledge',
            iconName: 'file-database',
            title: segment.title,
            status,
            badge,
            label: segment.title
        });
    }
    const body = renderDocumentCardBody(host, 'file-database', segment.title, status, badge);
    const label = host.escapeAttribute(i18n.t('chat.attachments.openKnowledge'));
    return `<button type="button" class="file-preview-item document chat-attachment-summary-card chat-attachment-summary-card--knowledge glass-surface-light glass-surface--bordered glass-surface--rounded" data-action="${host.escapeAttribute(CHAT_ACTIONS.OPEN_KNOWLEDGE_ATTACHMENT_PREVIEW)}" data-knowledge-attachment-id="${host.escapeAttribute(segment.knowledgeAttachmentId)}" data-knowledge-title="${host.escapeAttribute(segment.title)}" aria-label="${label}" data-tooltip="${label}">${body}</button>`;
};

const renderUnavailableCard = (host: ChatMessageRenderHost, segment: SoaiFileUnavailableSegment | SoaiKnowledgeUnavailableSegment): string => {
    const isFile = segment.type === 'soai_file_unavailable';
    const title = isFile ? segment.filename : segment.title;
    const unavailableLabel = i18n.t('chat.inlinePreviews.typeLabel.unavailable');
    const badgeLabel = isFile ? i18n.t('chat.attachments.badge.attachment') : i18n.t('chat.attachments.badge.knowledge');
    const badge = renderBadge(host, badgeLabel);
    return renderDocumentStaticCard(host, {
        className: isFile ? 'file-preview-item--unavailable chat-attachment-summary-card--attachment chat-attachment-summary-card--unavailable' : 'file-preview-item--unavailable chat-attachment-summary-card--knowledge chat-attachment-summary-card--unavailable',
        iconName: isFile ? resolveFileEntryIconName({ name: segment.filename, mimeType: segment.mimeType, isDirectory: false }) : 'file-database',
        title,
        status: unavailableLabel,
        badge,
        label: `${title}: ${unavailableLabel}`
    });
};

const renderAttachmentCard = (host: ChatMessageRenderHost, segment: AttachmentSummarySegment, options: MessageRenderOptions): string => {
    if (segment.type === 'soai_file') {
        return renderSoaiFileCard(host, segment, options);
    }
    if (segment.type === 'image') {
        return renderImageAttachmentCard(host, segment);
    }
    if (segment.type === 'soai_knowledge') {
        return renderSoaiKnowledgeCard(host, segment);
    }
    if (segment.type === 'soai_file_unavailable' || segment.type === 'soai_knowledge_unavailable') {
        return renderUnavailableCard(host, segment);
    }
    return renderSoaiPathCard(host, segment, options);
};

const renderOverflowCard = (host: ChatMessageRenderHost, hiddenCount: number): string => {
    const labelText = i18n.plural('chat.attachments.overflowHidden', hiddenCount, { count: hiddenCount });
    const label = host.escapeAttribute(labelText);
    const badge = renderBadge(host, labelText);
    const body = renderDocumentCardBody(host, 'ellipsis', labelText, '', badge);
    return `<button type="button" class="file-preview-item document chat-attachment-summary-card chat-attachment-summary-card--overflow glass-surface-light glass-surface--bordered glass-surface--rounded" data-action="${host.escapeAttribute(CHAT_ACTIONS.OPEN_ATTACHMENT_OVERFLOW)}" data-hidden-attachment-count="${host.escapeAttribute(String(hiddenCount))}" aria-label="${label}" data-tooltip="${label}">${body}</button>`;
};

const renderAttachmentStrip = (host: ChatMessageRenderHost, segments: AttachmentSummarySegment[], options: MessageRenderOptions): string => {
    const visible = segments.slice(0, CHAT_ATTACHMENT_INLINE_LIMIT);
    const hiddenCount = Math.max(0, segments.length - visible.length);
    const cards = visible.map((segment) => renderAttachmentCard(host, segment, options));
    if (hiddenCount > 0) {
        cards.push(renderOverflowCard(host, hiddenCount));
    }
    return `<div class="message-attachment-strip" data-attachment-count="${host.escapeAttribute(String(segments.length))}">${cards.join('')}</div>`;
};

export { isAttachmentSummarySegment, renderAttachmentCard, renderAttachmentStrip };
