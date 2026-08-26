/* SoAI - Chat feature message info modal rendering [frontend/assets/ts/features/chat/message/messageinfomodal/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isNumber, isString } from '@core/typeGuards.ts';
import { i18n } from '@core/i18n/index.ts';
import { resolveLatestLoadingActivityFromMessage } from '@features/chat/assistanteventtimeline/activityState.ts';
import { createAssistantTimelineIndexState } from '@features/chat/assistanteventtimeline/timelineIndexState.ts';
import { resolveAssistantTimelineOverlays } from '@features/chat/assistanteventtimeline/timelineIndexResolution.ts';
import { updateAssistantTimelineIndexState } from '@features/chat/assistanteventtimeline/timelineIndexUpdate.ts';
import { formatGenerationSpeed, formatLatency, formatTimestamp, formatToolActivityText, renderToolActivityHtml } from '@features/chat/message/messageinfomodal/mappers.ts';
import type { ChatMessage, MessageInfoEscapeDependencies, MessageInfoSectionContent, ToolActivityItem } from '@features/chat/message/messageinfomodal/types.ts';

type MessageInfoValueState = 'error' | 'success' | 'warning';

interface MessageInfoRowInput {
    label: string;
    value: string;
    mono?: boolean;
    valueState?: MessageInfoValueState;
}

const resolveToolActivity = (message: ChatMessage): ToolActivityItem[] => {
    const state = createAssistantTimelineIndexState();
    updateAssistantTimelineIndexState(state, message);
    const overlays = resolveAssistantTimelineOverlays(message, state);
    return overlays.toolActivity;
};

const buildMessageInfoRow = (label: string, value: string, mono: boolean = false, valueState: MessageInfoValueState | null = null): string => {
    const valueBaseClass = mono ? 'message-info-value message-info-value-mono' : 'message-info-value';
    const valueClass = valueState === null ? valueBaseClass : `${valueBaseClass} message-info-value--${valueState}`;
    return `<div class="message-info-row"><span class="message-info-label">${label}</span><span class="${valueClass}">${value}</span></div>`;
};

const appendMessageInfoRow = (
    dependencies: MessageInfoEscapeDependencies,
    rows: string[],
    copyLines: string[],
    inputArguments: {
        label: string;
        value: string;
        mono?: boolean;
        valueState?: MessageInfoValueState;
    }
): void => {
    rows.push(buildMessageInfoRow(dependencies.escapeHtml(inputArguments.label), dependencies.escapeHtml(inputArguments.value), inputArguments.mono === true, inputArguments.valueState ?? null));
    copyLines.push(`${inputArguments.label}: ${inputArguments.value}`);
};

const appendMessageInfoGridSection = (dependencies: MessageInfoEscapeDependencies, sections: string[], title: string, rows: string[]): void => {
    if (rows.length === 0) {
        return;
    }
    const escapedTitle = dependencies.escapeHtml(title);
    sections.push(`<div class="message-info-section"><div class="message-info-section-title">${escapedTitle}</div><div class="message-info-grid">${rows.join('')}</div></div>`);
};

const appendMessageInfoTextSection = (dependencies: MessageInfoEscapeDependencies, sections: string[], copyLines: string[], title: string, html: string, copyText: string | null): void => {
    if (!html) {
        return;
    }
    const escapedTitle = dependencies.escapeHtml(title);
    sections.push(`<div class="message-info-section"><div class="message-info-section-title">${escapedTitle}</div>${html}</div>`);
    if (copyText) {
        copyLines.push(`${title}:\n${copyText}`);
    }
};

const appendResolvedMessageInfoRows = (dependencies: MessageInfoEscapeDependencies, rows: string[], copyLines: string[], inputs: readonly (MessageInfoRowInput | null)[]): void => {
    for (const input of inputs) {
        if (input === null) {
            continue;
        }
        appendMessageInfoRow(dependencies, rows, copyLines, input);
    }
};

const resolveFinishReasonValueState = (finishReason: string): MessageInfoValueState => {
    const normalized = finishReason.trim().toLowerCase();
    if (normalized === 'error') {
        return 'error';
    }
    if (normalized === 'cancelled') {
        return 'warning';
    }
    return 'success';
};

const renderSectionContent = (dependencies: MessageInfoEscapeDependencies, message: ChatMessage): MessageInfoSectionContent => {
    const sections: string[] = [];
    const copyLines: string[] = [];
    const summaryRows: string[] = [];
    const loadingActivity = resolveLatestLoadingActivityFromMessage(message);
    const explicitMessageErrorCode = isString(message.errorCode) && message.errorCode.trim() ? message.errorCode.trim() : null;
    const derivedStreamErrorCode = (() => {
        if (explicitMessageErrorCode) {
            return explicitMessageErrorCode;
        }
        if (loadingActivity !== null && loadingActivity.status === 'error') {
            const errorType = loadingActivity.errorType;
            if (isString(errorType) && errorType.trim()) {
                return errorType.trim();
            }
        }
        return null;
    })();

    appendResolvedMessageInfoRows(dependencies, summaryRows, copyLines, [
        isString(message.modelId) && message.modelId
            ? {
                  label: i18n.t('chat.message.infoModal.model_id'),
                  value: message.modelId,
                  mono: true
              }
            : null,
        isNumber(message.timestamp) && message.timestamp > 0
            ? {
                  label: i18n.t('chat.message.infoModal.timestamp'),
                  value: formatTimestamp(message.timestamp),
                  mono: true
              }
            : null,
        isNumber(message.generationLatencyMs) && message.generationLatencyMs >= 0
            ? {
                  label: i18n.t('chat.message.infoModal.latency'),
                  value: formatLatency(message.generationLatencyMs),
                  mono: true
              }
            : null,
        isString(message.finishReason) && message.finishReason
            ? {
                  label: i18n.t('chat.message.infoModal.finishReason'),
                  value: message.finishReason,
                  mono: true,
                  valueState: resolveFinishReasonValueState(message.finishReason)
              }
            : null,
        isString(loadingActivity?.reason) && loadingActivity.reason.trim()
            ? {
                  label: i18n.t('chat.loading.reason'),
                  value: loadingActivity.reason.trim(),
                  mono: true
              }
            : null,
        isString(loadingActivity?.errorType) && loadingActivity.errorType.trim() && (explicitMessageErrorCode !== null || derivedStreamErrorCode !== loadingActivity.errorType.trim())
            ? {
                  label: i18n.t('chat.loading.errorType'),
                  value: loadingActivity.errorType.trim(),
                  mono: true
              }
            : null,
        derivedStreamErrorCode !== null
            ? {
                  label: i18n.t('chat.stream.error_code'),
                  value: derivedStreamErrorCode,
                  mono: true
              }
            : null
    ]);

    appendMessageInfoGridSection(dependencies, sections, i18n.t('chat.message.infoModal.summaryTitle'), summaryRows);

    const tokenRows: string[] = [];
    appendResolvedMessageInfoRows(dependencies, tokenRows, copyLines, [
        isNumber(message.promptTokens)
            ? {
                  label: i18n.t('chat.message.infoModal.promptTokens'),
                  value: String(message.promptTokens),
                  mono: true
              }
            : null,
        isNumber(message.completionTokens)
            ? {
                  label: i18n.t('chat.message.infoModal.completionTokens'),
                  value: String(message.completionTokens),
                  mono: true
              }
            : null,
        isNumber(message.totalTokens)
            ? {
                  label: i18n.t('chat.message.infoModal.totalTokens'),
                  value: String(message.totalTokens),
                  mono: true
              }
            : null,
        isNumber(message.generationSpeedTokensPerSec) && message.generationSpeedTokensPerSec > 0
            ? {
                  label: i18n.t('chat.message.infoModal.generationSpeed'),
                  value: formatGenerationSpeed(message.generationSpeedTokensPerSec),
                  mono: true
              }
            : null
    ]);
    appendMessageInfoGridSection(dependencies, sections, i18n.t('chat.message.infoModal.tokensTitle'), tokenRows);

    const compactionRows: string[] = [];
    const compactionStats = message.soaiCompactionStats;
    if (compactionStats && isNumber(compactionStats.count) && Number.isInteger(compactionStats.count) && compactionStats.count > 0) {
        appendResolvedMessageInfoRows(dependencies, compactionRows, copyLines, [
            {
                label: i18n.t('chat.message.infoModal.compactionCount'),
                value: String(compactionStats.count),
                mono: true
            },
            isNumber(compactionStats.tokensSaved) && Number.isInteger(compactionStats.tokensSaved) && compactionStats.tokensSaved >= 0
                ? {
                      label: i18n.t('chat.message.infoModal.compactionTokensSaved'),
                      value: String(compactionStats.tokensSaved),
                      mono: true
                  }
                : null
        ]);
    }
    appendMessageInfoGridSection(dependencies, sections, i18n.t('chat.message.infoModal.compactionTitle'), compactionRows);

    const toolActivity = resolveToolActivity(message);
    if (isArray(toolActivity) && toolActivity.length > 0) {
        const toolActivityTitle = i18n.t('chat.message.infoModal.toolActivity');
        appendMessageInfoTextSection(dependencies, sections, copyLines, toolActivityTitle, renderToolActivityHtml(dependencies, toolActivity), formatToolActivityText(toolActivity));
    }

    if (sections.length === 0) {
        const noDataText = dependencies.escapeHtml(i18n.t('chat.message.infoModal.noData'));
        sections.push(`<div class="message-info-nodata">${noDataText}</div>`);
    }

    return {
        html: sections.join(''),
        copyText: copyLines.length > 0 ? copyLines.join('\n') : null
    };
};

export { renderSectionContent };
