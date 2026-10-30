/* SoAI - Chat attach modal draft attachment list rows widget [frontend/assets/ts/features/attachmodal/draftRows.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { replaceChildrenFromTrustedHtml } from '@core/dom/html.ts';
import { reconcileChildNodes } from '@core/dom/childNodeReconciliation.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatBytes } from '@core/primitives/byteSize.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import type { AttachDraftDisplayRecord, AttachDraftEntry, AttachDraftPresentation } from '@features/attachmodal/draftContracts.ts';

const DRAFT_ATTACHMENT_ID_ATTRIBUTE = 'data-draft-attachment-id';
const DRAFT_ATTACHMENT_RENDER_SIGNATURE_ATTRIBUTE = 'data-draft-attachment-render-signature';

const resolveDraftAttachmentRenderSignature = (entry: AttachDraftEntry): string => {
    const attachment = entry.attachment;
    return JSON.stringify([attachment.name, attachment.parseStatus, attachment.parseError, attachment.missingCapabilities, attachment.mimeType, attachment.type, attachment.sizeBytes, attachment.size, attachment.isImage, entry.previewUrl, entry.iconName]);
};

const resolveDraftAttachmentMetaText = (attachment: AttachDraftDisplayRecord): string => {
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

const createDraftAttachmentListRow = (documentRef: Document, entry: AttachDraftEntry, presentation: AttachDraftPresentation): HTMLElement => {
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
    name.dir = 'auto';
    name.textContent = attachment.name;
    const statusInfo = presentation.status(attachment);
    const badge = documentRef.createElement('span');
    badge.className = `ui-status-badge ${statusInfo.className}`;
    badge.textContent = statusInfo.label;
    header.append(name);
    info.append(header);
    const metaText = resolveDraftAttachmentMetaText(attachment);
    if (metaText) {
        const meta = documentRef.createElement('div');
        meta.className = 'chat-attach-draft-attachment-row-meta';
        meta.dir = 'ltr';
        meta.textContent = metaText;
        info.append(meta);
    }
    if (attachment.parseStatus === 'error' && attachment.parseError) {
        const detail = documentRef.createElement('div');
        detail.className = 'chat-attach-draft-attachment-row-detail';
        detail.dir = 'auto';
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
    removeButton.dataset['action'] = 'attach-draft:remove';
    removeButton.setAttribute('aria-label', removeLabel);
    setTooltipText(removeButton, removeLabel);
    replaceChildrenFromTrustedHtml({ element: removeButton, html: getIconSync('close', { size: 14, strokeWidth: 1.5 }), context: removeButton });
    actions.append(removeButton);
    header.append(actions);
    row.append(presentation.createVisual(documentRef, entry), info);
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

const patchDraftAttachmentListRow = (current: HTMLElement, next: HTMLElement, presentation: AttachDraftPresentation): boolean => {
    const preservesVisual = presentation.preserveVisuals(current, next);
    current.setAttribute(DRAFT_ATTACHMENT_RENDER_SIGNATURE_ATTRIBUTE, next.getAttribute(DRAFT_ATTACHMENT_RENDER_SIGNATURE_ATTRIBUTE) ?? '');
    reconcileChildNodes(current, Array.from(next.childNodes));
    return !preservesVisual && presentation.hasThumbnails(current);
};

const reconcileDraftAttachmentListRows = (list: HTMLElement, entries: readonly AttachDraftEntry[], presentation: AttachDraftPresentation): { structureChanged: boolean; thumbnailsChanged: boolean } => {
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
            row = createDraftAttachmentListRow(list.ownerDocument, entry, presentation);
            thumbnailsChanged = presentation.hasThumbnails(row) || thumbnailsChanged;
        } else if (row.getAttribute(DRAFT_ATTACHMENT_RENDER_SIGNATURE_ATTRIBUTE) !== resolveDraftAttachmentRenderSignature(entry)) {
            thumbnailsChanged = patchDraftAttachmentListRow(row, createDraftAttachmentListRow(list.ownerDocument, entry, presentation), presentation) || thumbnailsChanged;
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
