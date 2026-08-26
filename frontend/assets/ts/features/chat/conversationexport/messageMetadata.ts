/* SoAI - Conversation export message metadata rendering [frontend/assets/ts/features/chat/conversationexport/messageMetadata.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatInvariantNumber } from '@core/localization/public.ts';
import { formatCompactDurationFromMs } from '@core/primitives/duration.ts';
import { isFiniteNumber, isString } from '@core/typeGuards.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { resolveConversationExportActivitySummary } from '@features/chat/conversationexport/activitySummary.ts';
import { buildMessageContentSegments } from '@features/chat/message/messageSegmentsFromContent.ts';

type ConversationExportMetadataHost = {
    html(value: string): string;
};

const pushTextField = (fields: string[], label: string, value: string | null | undefined): void => {
    const trimmed = isString(value) ? value.trim() : '';
    if (trimmed) {
        fields.push(`${label}: ${trimmed}`);
    }
};

const pushNumberField = (fields: string[], label: string, value: number | null | undefined): void => {
    if (isFiniteNumber(value) && value > 0) {
        fields.push(`${label}: ${String(Math.floor(value))}`);
    }
};

const pushDurationField = (fields: string[], label: string, value: number | null | undefined): void => {
    if (isFiniteNumber(value) && value > 0) {
        fields.push(`${label}: ${formatCompactDurationFromMs(Math.floor(value))}`);
    }
};

const renderConversationExportMessageMetadata = (host: ConversationExportMetadataHost, message: ChatMessage): string => {
    const fields: string[] = [];
    const segments = buildMessageContentSegments(message.content);
    const activitySummary = resolveConversationExportActivitySummary(message, segments);
    pushTextField(fields, i18n.t('chat.export.pdf.messageMetadata.model'), message.modelId);
    pushTextField(fields, i18n.t('chat.export.pdf.messageMetadata.requestId'), message.requestId);
    pushTextField(fields, i18n.t('chat.export.pdf.messageMetadata.finishReason'), message.finishReason);
    pushNumberField(fields, i18n.t('chat.export.pdf.messageMetadata.promptTokens'), message.promptTokens);
    pushNumberField(fields, i18n.t('chat.export.pdf.messageMetadata.completionTokens'), message.completionTokens);
    pushNumberField(fields, i18n.t('chat.export.pdf.messageMetadata.totalTokens'), message.totalTokens);
    pushDurationField(fields, i18n.t('chat.export.pdf.messageMetadata.latency'), message.generationLatencyMs);
    if (isFiniteNumber(message.generationSpeedTokensPerSec) && message.generationSpeedTokensPerSec > 0) {
        const speed = i18n.t('chat.export.pdf.messageMetadata.tokensPerSecond', { value: formatInvariantNumber(message.generationSpeedTokensPerSec, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) });
        fields.push(`${i18n.t('chat.export.pdf.messageMetadata.speed')}: ${speed}`);
    }
    if (fields.length === 0) {
        if (activitySummary.labels.length === 0) {
            return '';
        }
        const activityText = `${i18n.t('chat.export.pdf.messageMetadata.activities')}: ${activitySummary.labels.join(', ')}`;
        return `<div class="chat-export-message-activity-metadata"><span>${host.html(activityText)}</span></div>`;
    }
    const metadata = `<div class="chat-export-message-metadata">${fields.map((field) => `<span>${host.html(field)}</span>`).join('')}</div>`;
    if (activitySummary.labels.length === 0) {
        return metadata;
    }
    const activityText = `${i18n.t('chat.export.pdf.messageMetadata.activities')}: ${activitySummary.labels.join(', ')}`;
    return `${metadata}<div class="chat-export-message-activity-metadata"><span>${host.html(activityText)}</span></div>`;
};

export { renderConversationExportMessageMetadata };
