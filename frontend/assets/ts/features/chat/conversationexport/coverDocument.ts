/* SoAI - Conversation export cover document builder [frontend/assets/ts/features/chat/conversationexport/coverDocument.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { escapeHtml } from '@core/security/textSanitizer.ts';
import type { ConversationExportCoverData, ConversationExportOutlineEntry, ConversationExportSummaryItem } from '@features/chat/conversationexport/coverData.ts';
import { CONVERSATION_EXPORT_COVER_STYLE } from '@features/chat/conversationexport/coverStyles.ts';

type ConversationExportCoverDocumentRequest = {
    title: string;
    exportDate: string;
    logoDataUri: string;
    soaiVersion: string | null;
    coverData: ConversationExportCoverData;
};

const OUTLINE_INDEX_DIGITS = 2;

const renderStat = (item: ConversationExportSummaryItem): string => `<div class="stat"><span class="stat-label">${escapeHtml(item.label)}</span><span class="stat-value">${escapeHtml(item.value)}</span></div>`;

const renderOutlineRow = (entry: ConversationExportOutlineEntry): string => `<li class="outline-row"><span class="outline-index">${escapeHtml(String(entry.index).padStart(OUTLINE_INDEX_DIGITS, '0'))}</span><span class="outline-role outline-role--${entry.kind}">${escapeHtml(entry.role)}</span><span class="outline-text">${escapeHtml(entry.preview)}</span></li>`;

const renderOutlineSection = (outline: readonly ConversationExportOutlineEntry[]): string => {
    if (outline.length === 0) {
        return '';
    }
    const rows = outline.map(renderOutlineRow).join('');
    return `<section class="cover-outline"><h2 class="cover-section-title">${escapeHtml(i18n.t('chat.export.pdf.cover.outlineTitle'))}</h2><ol class="outline-list">${rows}</ol></section>`;
};

const renderOriginLine = (origin: string): string => (origin ? `<p class="cover-origin">${escapeHtml(origin)}</p>` : '');

const renderNote = (exportDate: string, soaiVersion: string | null): string => {
    if (soaiVersion === null) {
        return i18n.t('chat.export.pdf.exportedNoteWithoutVersion', { date: exportDate });
    }
    return i18n.t('chat.export.pdf.exportedNote', { version: soaiVersion, date: exportDate });
};

const buildConversationExportCoverDocument = (request: ConversationExportCoverDocumentRequest): string => {
    return ['<!doctype html><html><head><meta charset="utf-8">', `<title>${escapeHtml(request.title)}</title>`, `<style>${CONVERSATION_EXPORT_COVER_STYLE}</style>`, '</head><body><main class="cover">', '<header class="cover-masthead">', `<div class="cover-brand"><img src="${escapeHtml(request.logoDataUri)}"></div>`, '<div class="cover-head">', `<p class="cover-kicker">${escapeHtml(i18n.t('chat.export.pdf.title'))}</p>`, `<h1 class="cover-title">${escapeHtml(request.title)}</h1>`, renderOriginLine(request.coverData.origin), '</div></header>', renderOutlineSection(request.coverData.outline), `<section class="cover-stats">${request.coverData.summaryItems.map(renderStat).join('')}</section>`, `<footer class="cover-note">${escapeHtml(renderNote(request.exportDate, request.soaiVersion))}</footer>`, '</main></body></html>'].join('');
};

export { buildConversationExportCoverDocument };
export type { ConversationExportCoverDocumentRequest };
