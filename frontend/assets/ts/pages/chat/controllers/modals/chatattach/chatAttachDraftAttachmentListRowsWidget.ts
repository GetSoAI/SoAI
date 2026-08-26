/* SoAI - Chat attach modal draft attachment list rows widget [frontend/assets/ts/pages/chat/controllers/modals/chatattach/chatAttachDraftAttachmentListRowsWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { replaceChildrenFromTrustedHtml } from '@core/dom/html.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatBytes } from '@core/primitives/byteSize.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import type { ChatAttachment } from '@features/chat/public.ts';

const resolveDraftAttachmentStatusPresentation = (attachment: ChatAttachment): { label: string; className: string } => {
    if (attachment.parseStatus === 'ready') {
        return { label: i18n.t('chat.attachments.status.ready'), className: 'status-green' };
    }
    if (attachment.parseStatus === 'processing') {
        return { label: i18n.t('chat.attachments.status.processing'), className: 'status-blue' };
    }
    return { label: i18n.t('chat.attachments.status.error'), className: 'status-red' };
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

const createDraftAttachmentListRow = (documentRef: Document, attachment: ChatAttachment): HTMLElement => {
    const row = documentRef.createElement('div');
    row.className = 'chat-attach-draft-attachment-row';
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
    header.append(name, badge);
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
    const removeButton = documentRef.createElement('button');
    const removeLabel = i18n.t('chat.attachments.removeTooltip');
    removeButton.type = 'button';
    removeButton.className = 'ui-round-button ui-round-button--inline ui-round-button--delete chat-attach-draft-attachment-row-delete';
    removeButton.dataset['fileId'] = attachment.id;
    removeButton.setAttribute('aria-label', removeLabel);
    setTooltipText(removeButton, removeLabel);
    replaceChildrenFromTrustedHtml({ element: removeButton, html: getIconSync('close', { size: 14, strokeWidth: 1.5 }), context: removeButton });
    actions.append(removeButton);
    row.append(info, actions);
    return row;
};

export { createDraftAttachmentListRow };
