/* SoAI - Conversation export compaction boundary rendering [frontend/assets/ts/features/chat/conversationexport/compactionBoundaryRendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { isArray, isBoolean, isObject, isString } from '@core/typeGuards.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';

type ConversationExportCompactionHost = {
    html(value: string): string;
};

const resolveCompactionStatus = (message: ChatMessage): string => {
    const marker = message.soaiCompaction;
    if (!isObject(marker) || isArray(marker)) {
        return i18n.t('chat.export.pdf.compaction.status.recorded');
    }
    const status = marker.status;
    if (isString(status) && status.trim()) {
        return status.trim();
    }
    return i18n.t('chat.export.pdf.compaction.status.recorded');
};

const resolveCompactionBoundaryState = (message: ChatMessage): string => {
    const marker = message.soaiCompaction;
    if (!isObject(marker) || isArray(marker)) {
        return '';
    }
    const active = marker.isActiveBoundary;
    if (!isBoolean(active)) {
        return '';
    }
    return active ? i18n.t('chat.export.pdf.compaction.boundaryActive') : i18n.t('chat.export.pdf.compaction.boundaryInactive');
};

const renderCompactionBoundaryIntro = (host: ConversationExportCompactionHost, message: ChatMessage): string => {
    const status = resolveCompactionStatus(message);
    const boundaryState = resolveCompactionBoundaryState(message);
    const parts = boundaryState ? [status, boundaryState] : [status];
    const meta = parts.map((part) => `<span>${host.html(part)}</span>`).join('');
    return `<div class="chat-export-compaction-meta">${meta}</div>`;
};

const renderCompactionFallback = (host: ConversationExportCompactionHost): string => {
    return `<p class="chat-export-compaction-fallback">${host.html(i18n.t('chat.export.pdf.compaction.fallback'))}</p>`;
};

const renderConversationExportCompactionBody = (host: ConversationExportCompactionHost, message: ChatMessage, bodyHtml: string): string => {
    const content = bodyHtml.trim() ? bodyHtml : renderCompactionFallback(host);
    return `${renderCompactionBoundaryIntro(host, message)}${content}`;
};

export { renderConversationExportCompactionBody };
