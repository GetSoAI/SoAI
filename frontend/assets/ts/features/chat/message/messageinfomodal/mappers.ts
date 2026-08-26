/* SoAI - Chat feature message info modal mapping [frontend/assets/ts/features/chat/message/messageinfomodal/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNumber } from '@core/typeGuards.ts';
import { formatInvariantNumber } from '@core/localization/public.ts';
import { formatDateTimeSecond } from '@core/primitives/dateTime.ts';
import { formatCompactDurationFromMs, formatDurationSeconds } from '@core/primitives/duration.ts';
import { i18n } from '@core/i18n/index.ts';
import type { MessageInfoEscapeDependencies, ToolActivityItem } from '@features/chat/message/messageinfomodal/types.ts';
import { CHAT_TOOL_ACTIVITY_STATUSES } from '@features/chat/message/messageinfomodal/constants.ts';
import { resolveToolActivityStatusLabel } from '@features/chat/message/toolActivityStatusLabel.ts';

interface ResolvedToolActivityItem {
    durationLabel: string | null;
    name: string;
    status: string;
    statusLabel: string;
}

const formatTimestamp = (timestamp: number): string => formatDateTimeSecond(timestamp);

const formatLatency = (latencyMs: number): string => i18n.t('chat.message.infoModal.latencySec', { seconds: formatDurationSeconds(latencyMs) });

const formatGenerationSpeed = (tokensPerSec: number): string => i18n.t('chat.message.infoModal.tokensPerSecond', { rate: formatInvariantNumber(tokensPerSec, { maximumFractionDigits: 2 }) });

const resolveToolActivityItems = (toolActivity: ToolActivityItem[]): ResolvedToolActivityItem[] => {
    return toolActivity
        .filter((tool) => CHAT_TOOL_ACTIVITY_STATUSES.has(tool.status))
        .map((tool) => ({
            durationLabel: isNumber(tool.durationMs) ? formatCompactDurationFromMs(tool.durationMs) : null,
            name: tool.toolName,
            status: tool.status,
            statusLabel: resolveToolActivityStatusLabel(tool.status)
        }));
};

const formatToolActivityText = (toolActivity: ToolActivityItem[]): string => {
    const lines = resolveToolActivityItems(toolActivity).map((tool) => {
        const duration = tool.durationLabel ? `(${tool.durationLabel})` : '';
        return `${tool.name}: ${tool.statusLabel} ${duration}`.trim();
    });
    if (lines.length === 0) {
        return '';
    }
    return lines.join('\n');
};

const renderToolActivityHtml = (dependencies: MessageInfoEscapeDependencies, toolActivity: ToolActivityItem[]): string => {
    const items = resolveToolActivityItems(toolActivity).map((tool) => {
        const name = dependencies.escapeHtml(tool.name);
        const statusLabel = dependencies.escapeHtml(tool.statusLabel);
        const statusClass = tool.status === 'error' ? 'message-info-tool-status message-info-tool-status--error' : 'message-info-tool-status';
        const duration = tool.durationLabel ? `<span>${dependencies.escapeHtml(tool.durationLabel)}</span>` : '';
        return `<div class="message-info-tool-item"><span class="message-info-tool-name">${name}</span><div class="message-info-tool-details">${duration}<span class="${statusClass}">${statusLabel}</span></div></div>`;
    });
    if (items.length === 0) return '';
    return `<div class="message-info-tools-list">${items.join('')}</div>`;
};

export { formatTimestamp, formatLatency, formatGenerationSpeed, formatToolActivityText, renderToolActivityHtml };
