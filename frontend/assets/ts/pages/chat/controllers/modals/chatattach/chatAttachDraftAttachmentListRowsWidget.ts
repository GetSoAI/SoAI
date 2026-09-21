/* SoAI - Chat attach modal draft attachment list rows widget [frontend/assets/ts/pages/chat/controllers/modals/chatattach/chatAttachDraftAttachmentListRowsWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { replaceChildrenFromTrustedHtml } from '@core/dom/html.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatBytes } from '@core/primitives/byteSize.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { hasAttachmentThumbnail, preserveStableAttachmentThumbnailVisuals, resolveDraftAttachmentStatusLabel, type ChatAttachment } from '@features/chat/public.ts';
import type { ChatAttachDraftAttachmentListEntry } from '@pages/chat/controllers/modals/chatattach/types.ts';

const DRAFT_ATTACHMENT_ID_ATTRIBUTE = 'data-draft-attachment-id';
const DRAFT_ATTACHMENT_RENDER_SIGNATURE_ATTRIBUTE = 'data-draft-attachment-render-signature';

const resolveDraftAttachmentStatusPresentation = (attachment: ChatAttachment): { label: string; className: string } => {
    if (attachment.parseStatus === 'ready') {
        return { label: resolveDraftAttachmentStatusLabel(attachment.parseStatus), className: 'status-green' };
    }
    if (attachment.parseStatus === 'processing') {
        return { label: resolveDraftAttachmentStatusLabel(attachment.parseStatus), className: 'status-blue' };
    }
    return { label: resolveDraftAttachmentStatusLabel(attachment.parseStatus), className: 'status-red' };
};

const resolveDraftAttachmentRenderSignature = (entry: ChatAttachDraftAttachmentListEntry): string => {
    const attachment = entry.attachment;
    return JSON.stringify([attachment.name, attachment.parseStatus, attachment.parseError, attachment.mimeType, attachment.type, attachment.sizeBytes, attachment.size, attachment.isImage, entry.previewUrl, entry.iconName]);
};

const resolveDraftAttachmentMetaText = (attachment: ChatAttachment): string => {
    const parts: string[] = [];
    const typeLabel = (attachment.mimeType ?? attachment.type ?? '').trim();
    if (typeLabel) {
        parts.push(typeLabel);
    }
    const sizeValue = attachment.sizeBytes ?? attachment.size;
    if (Number.isFinite(sizeValue) && sizeValue > 0) {
        parts.push(formatBytes(sizeValue));
    }
    return parts.join(' • ');
};

const createDraftAttachmentVisual = (documentRef: Document, entry: ChatAttachDraftAttachmentListEntry): HTMLElement => {
    const icon = documentRef.createElement('span');
    icon.className = 'file-preview-leading-icon';
    icon.setAttribute('aria-hidden', 'true');
    replaceChildrenFromTrustedHtml({ element: icon, html: getIconSync(entry.iconName, { size: 20, strokeWidth: 1.5 }), context: icon });
    if (!entry.attachment.isImage) {
        return icon;
    }
    const visual = documentRef.createElement('span');
    visual.className = 'chat-attachment-visual';
    visual.setAttribute('data-attachment-image-state', entry.previewUrl === null ? 'error' : 'loading');
    visual.append(icon);
    if (entry.previewUrl !== null) {
        const image = documentRef.createElement('img');
        image.src = entry.previewUrl;
        image.alt = '';
        image.loading = 'lazy';
        image.decoding = 'async';
        image.setAttribute('data-chat-attachment-thumbnail', 'true');
        visual.append(image);
    }
    return visual;
};

const createDraftAttachmentListRow = (documentRef: Document, entry: ChatAttachDraftAttachmentListEntry): HTMLElement => {
    const attachment = entry.attachment;
    const row = documentRef.createElement('div');
    row.className = 'chat-attach-draft-attachment-row';
    row.setAttribute(DRAFT_ATTACHMENT_ID_ATTRIBUTE, attachment.id);
    row.setAttribute(DRAFT_ATTACHMENT_RENDER_SIGNATURE_ATTRIBUTE, resolveDraftAttachmentRenderSignature(entry));
    const info = documentRef.createElement('div');
    info.className = 'chat-attach-draft-attachment-row-info';
    const header = documentRef.createElement('div');
    header.className = 'chat-attach-draft-attachment-row-header';
    const name = documentRef.createElement('div');
    name.className = 'chat-attach-draft-attachment-row-name';
    name.textContent = attachment.name;
    const statusInfo = resolveDraftAttachmentStatusPresentation(attachment);
    const badge = documentRef.createElement('span');
    badge.className = `ui-status-badge ${statusInfo.className}`;
    badge.textContent = statusInfo.label;
    header.append(name);
    info.append(header);
    const metaText = resolveDraftAttachmentMetaText(attachment);
    if (metaText) {
        const meta = documentRef.createElement('div');
        meta.className = 'chat-attach-draft-attachment-row-meta';
        meta.textContent = metaText;
        info.append(meta);
    }
    if (attachment.parseStatus === 'error' && attachment.parseError) {
        const detail = documentRef.createElement('div');
        detail.className = 'chat-attach-draft-attachment-row-detail';
        detail.textContent = attachment.parseError;
        info.append(detail);
    }
    const actions = documentRef.createElement('div');
    actions.className = 'chat-attach-draft-attachment-row-actions';
    actions.append(badge);
    const removeButton = documentRef.createElement('button');
    const removeLabel = i18n.t('chat.attachments.removeTooltip');
    removeButton.type = 'button';
    removeButton.className = 'ui-round-button ui-round-button--inline ui-round-button--delete chat-attach-draft-attachment-row-delete';
    removeButton.dataset['fileId'] = attachment.id;
    removeButton.setAttribute('aria-label', removeLabel);
    setTooltipText(removeButton, removeLabel);
    replaceChildrenFromTrustedHtml({ element: removeButton, html: getIconSync('close', { size: 14, strokeWidth: 1.5 }), context: removeButton });
    actions.append(removeButton);
    row.append(createDraftAttachmentVisual(documentRef, entry), info, actions);
    return row;
};

const collectDraftAttachmentRows = (list: HTMLElement): Map<string, HTMLElement> => {
    const rows = new Map<string, HTMLElement>();
    for (const child of list.children) {
        if (!(child instanceof HTMLElement)) {
            continue;
        }
        const attachmentId = child.getAttribute(DRAFT_ATTACHMENT_ID_ATTRIBUTE);
        if (attachmentId === null || !attachmentId.trim() || rows.has(attachmentId)) {
            throw new Error('Draft attachment list contains an invalid or duplicate row identity');
        }
        rows.set(attachmentId, child);
    }
    return rows;
};

const patchDraftAttachmentListRow = (current: HTMLElement, next: HTMLElement): boolean => {
    const preservesVisual = preserveStableAttachmentThumbnailVisuals(current, next) > 0;
    current.setAttribute(DRAFT_ATTACHMENT_RENDER_SIGNATURE_ATTRIBUTE, next.getAttribute(DRAFT_ATTACHMENT_RENDER_SIGNATURE_ATTRIBUTE) ?? '');
    current.replaceChildren(...Array.from(next.childNodes));
    return !preservesVisual && hasAttachmentThumbnail(current);
};

const reconcileDraftAttachmentListRows = (list: HTMLElement, entries: readonly ChatAttachDraftAttachmentListEntry[]): { structureChanged: boolean; thumbnailsChanged: boolean } => {
    const existingRows = collectDraftAttachmentRows(list);
    const retainedIds = new Set<string>();
    let structureChanged = existingRows.size !== entries.length;
    let thumbnailsChanged = false;
    for (const [index, entry] of entries.entries()) {
        const attachmentId = entry.attachment.id;
        if (retainedIds.has(attachmentId)) {
            throw new Error(`Draft attachment list received duplicate attachment id: ${attachmentId}`);
        }
        retainedIds.add(attachmentId);
        const current = existingRows.get(attachmentId);
        let row = current;
        if (row === undefined) {
            row = createDraftAttachmentListRow(list.ownerDocument, entry);
            thumbnailsChanged = hasAttachmentThumbnail(row) || thumbnailsChanged;
        } else if (row.getAttribute(DRAFT_ATTACHMENT_RENDER_SIGNATURE_ATTRIBUTE) !== resolveDraftAttachmentRenderSignature(entry)) {
            thumbnailsChanged = patchDraftAttachmentListRow(row, createDraftAttachmentListRow(list.ownerDocument, entry)) || thumbnailsChanged;
        }
        const expectedRow = list.children.item(index);
        if (expectedRow !== row) {
            list.insertBefore(row, expectedRow);
            structureChanged = true;
        }
    }
    for (const [attachmentId, row] of existingRows.entries()) {
        if (!retainedIds.has(attachmentId)) {
            row.remove();
        }
    }
    return { structureChanged, thumbnailsChanged };
};

export { createDraftAttachmentListRow, reconcileDraftAttachmentListRows };
