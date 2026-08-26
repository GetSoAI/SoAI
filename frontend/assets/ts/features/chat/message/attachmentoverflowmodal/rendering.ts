/* SoAI - Chat attachment overflow modal row rendering [frontend/assets/ts/features/chat/message/attachmentoverflowmodal/rendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { securityApi } from '@core/security/public.ts';
import { getBadgeColorClass } from '@core/ui/badgeColors.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import type { AttachmentOverflowRecord } from '@features/chat/message/attachmentoverflowmodal/records.ts';

const resolveBadgeText = (type: AttachmentOverflowRecord['type']): string => {
    if (type === 'attachment') {
        return i18n.t('chat.attachments.badge.attachment');
    }
    if (type === 'knowledge' || type === 'knowledgeItem') {
        return i18n.t('chat.attachments.badge.knowledge');
    }
    return i18n.t('chat.attachments.badge.soaiLink');
};

const appendRecordPreview = (row: HTMLElement, record: AttachmentOverflowRecord): void => {
    if (record.previewUrl === null) {
        return;
    }
    const src = securityApi.sanitizeImageSource(record.previewUrl);
    if (src === null) {
        throw new Error('Attachment overflow preview URL failed sanitization');
    }
    const image = dom.getDocument().createElement('img');
    image.src = src;
    image.alt = record.title;
    image.loading = 'lazy';
    image.decoding = 'async';
    row.append(image);
};

const configureButtonRow = (row: HTMLButtonElement, record: AttachmentOverflowRecord): void => {
    row.type = 'button';
    row.setAttribute('aria-label', record.title);
    setTooltipText(row, record.title);
    if (record.knowledgeAttachmentId !== null) {
        row.dataset['attachmentOverflowAction'] = 'knowledge-preview-first';
        row.dataset['knowledgeAttachmentId'] = record.knowledgeAttachmentId;
    }
};

const configureKnowledgeItemRow = (row: HTMLButtonElement, record: AttachmentOverflowRecord): void => {
    row.type = 'button';
    row.setAttribute('aria-label', record.title);
    if (record.unavailableReason !== null) {
        row.disabled = true;
        row.setAttribute('aria-disabled', 'true');
        setTooltipText(row, record.unavailableReason);
        return;
    }
    row.dataset['attachmentOverflowAction'] = 'knowledge-preview';
    row.dataset['collectionId'] = record.id;
    setTooltipText(row, record.title);
};

const configureSoaiPathRow = (row: HTMLButtonElement, record: AttachmentOverflowRecord): void => {
    row.type = 'button';
    row.setAttribute('aria-label', record.title);
    row.dataset['attachmentOverflowAction'] = 'soai-path-preview';
    row.dataset['collectionId'] = record.id;
    setTooltipText(row, record.title);
};

const configureAnchorRow = (row: HTMLAnchorElement, record: AttachmentOverflowRecord): void => {
    if (record.href === null) {
        throw new Error('Attachment overflow anchor row requires an href');
    }
    row.href = record.href;
    row.target = '_blank';
    row.rel = 'noopener noreferrer';
    row.setAttribute('aria-label', record.title);
    setTooltipText(row, record.title);
};

const configureStaticRow = (row: HTMLElement, record: AttachmentOverflowRecord): void => {
    const label = record.unavailableReason === null ? record.title : `${record.title}: ${record.unavailableReason}`;
    row.setAttribute('aria-label', label);
    setTooltipText(row, label);
};

const appendDraftKnowledgeDeleteButton = (row: HTMLElement, record: AttachmentOverflowRecord): void => {
    if (!record.draftRemovable || record.knowledgeAttachmentId === null) {
        return;
    }
    const button = dom.getDocument().createElement('button');
    button.type = 'button';
    button.className = 'ui-round-button ui-round-button--inline ui-round-button--delete chat-attachment-overflow-delete';
    button.dataset['attachmentOverflowAction'] = 'knowledge-remove-draft';
    button.dataset['knowledgeAttachmentId'] = record.knowledgeAttachmentId;
    const label = i18n.t('chat.attachments.removeTooltip');
    button.setAttribute('aria-label', label);
    setTooltipText(button, label);
    dom.setHTML(button, getIconSync('close', { size: 14, strokeWidth: 1.5 }), { escape: false });
    row.append(button);
};

const renderRemovableKnowledgeRow = (record: AttachmentOverflowRecord): HTMLDivElement => {
    const row = dom.getDocument().createElement('div');
    row.className = 'file-preview-item document chat-attachment-overflow-item chat-attachment-overflow-item--knowledge chat-attachment-overflow-item--removable glass-surface-light glass-surface--bordered glass-surface--rounded';
    row.dataset['collectionId'] = record.id;
    configureStaticRow(row, record);
    const body = dom.getDocument().createElement('button');
    body.type = 'button';
    body.className = 'chat-attachment-overflow-body';
    body.dataset['attachmentOverflowAction'] = 'knowledge-preview-first';
    if (record.knowledgeAttachmentId !== null) {
        body.dataset['knowledgeAttachmentId'] = record.knowledgeAttachmentId;
    }
    body.setAttribute('aria-label', record.title);
    setTooltipText(body, record.title);
    appendRecordPreview(body, record);
    appendRecordInfo(body, record);
    row.append(body);
    appendDraftKnowledgeDeleteButton(row, record);
    return row;
};

const appendRecordInfo = (row: HTMLElement, record: AttachmentOverflowRecord): void => {
    const info = dom.getDocument().createElement('div');
    info.className = 'file-info';
    const name = dom.getDocument().createElement('span');
    name.className = 'file-name';
    name.textContent = record.title;
    const status = dom.getDocument().createElement('span');
    status.className = 'file-status';
    const badge = dom.getDocument().createElement('span');
    const badgeText = resolveBadgeText(record.type);
    badge.className = `chat-attachment-badge ui-model-type-badge ui-badge--micro ${getBadgeColorClass(`chat-attachment:${badgeText}`)}`;
    badge.textContent = badgeText;
    const statusText = dom.getDocument().createElement('span');
    statusText.textContent = record.unavailableReason === null ? record.status : [record.status, record.unavailableReason].filter((value) => value.length > 0).join(' - ');
    status.append(badge, statusText);
    info.append(name, status);
    row.append(info);
};

const renderAttachmentOverflowItem = (record: AttachmentOverflowRecord): HTMLElement => {
    if (record.type === 'knowledgeItem') {
        const row = dom.getDocument().createElement('button');
        row.className = `file-preview-item ${record.previewUrl === null ? 'document' : 'image'} chat-attachment-overflow-item chat-attachment-overflow-item--${record.type} glass-surface-light glass-surface--bordered glass-surface--rounded`;
        configureKnowledgeItemRow(row, record);
        appendRecordPreview(row, record);
        appendRecordInfo(row, record);
        return row;
    }
    if (record.type === 'soaiLink' && record.soaiPathContentPart !== null) {
        const row = dom.getDocument().createElement('button');
        row.className = `file-preview-item ${record.previewUrl === null ? 'document' : 'image'} chat-attachment-overflow-item chat-attachment-overflow-item--${record.type} glass-surface-light glass-surface--bordered glass-surface--rounded`;
        configureSoaiPathRow(row, record);
        appendRecordPreview(row, record);
        appendRecordInfo(row, record);
        return row;
    }
    if (record.href === null && record.knowledgeAttachmentId !== null) {
        if (record.draftRemovable) {
            return renderRemovableKnowledgeRow(record);
        }
        const row = dom.getDocument().createElement('button');
        row.className = `file-preview-item ${record.previewUrl === null ? 'document' : 'image'} chat-attachment-overflow-item chat-attachment-overflow-item--${record.type} glass-surface-light glass-surface--bordered glass-surface--rounded`;
        row.dataset['collectionId'] = record.id;
        configureButtonRow(row, record);
        appendRecordPreview(row, record);
        appendRecordInfo(row, record);
        return row;
    }
    if (record.href === null) {
        const row = dom.getDocument().createElement('div');
        row.className = `file-preview-item ${record.previewUrl === null ? 'document' : 'image'} chat-attachment-overflow-item chat-attachment-overflow-item--${record.type} glass-surface-light glass-surface--bordered glass-surface--rounded`;
        row.dataset['collectionId'] = record.id;
        configureStaticRow(row, record);
        appendRecordPreview(row, record);
        appendRecordInfo(row, record);
        return row;
    }
    const row = dom.getDocument().createElement('a');
    row.className = `file-preview-item ${record.previewUrl === null ? 'document' : 'image'} chat-attachment-overflow-item chat-attachment-overflow-item--${record.type} glass-surface-light glass-surface--bordered glass-surface--rounded`;
    row.dataset['collectionId'] = record.id;
    configureAnchorRow(row, record);
    appendRecordPreview(row, record);
    appendRecordInfo(row, record);
    return row;
};

export { renderAttachmentOverflowItem };
