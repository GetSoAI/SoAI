/* SoAI - Inline tool activity detail rendering [frontend/assets/ts/features/chat/message/messageview/inlineToolActivityDetails.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { formatCompactDurationFromMs } from '@core/primitives/duration.ts';
import { isEpochMsNumber } from '@core/time/epochMs.ts';
import { isJsonValue, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { CHAT_ACTIONS } from '@features/chat/chatActionIds.ts';
import { INLINE_ACTIVITY_DETAILS_SIGNATURE_ATTRIBUTE } from '@features/chat/message/inlineActivityDetailsIdentity.ts';
import { CONTEXT_COMPACTION_TOOL_LEAF, isManualContextCompactionCallId, isRemovedContextCompactionResult } from '@features/chat/message/contextcompaction/detection.ts';
import { renderContextCompactionToolResult } from '@features/chat/message/contextcompaction/resultRendering.ts';
import { renderInlineToolCodeDiffs } from '@features/chat/message/messageview/inlineToolCodeDiffRendering.ts';
import { resolveInlineToolActivityPresentation, resolveInlineToolStatusSummaryText, type InlineToolActivityPresentation } from '@features/chat/message/messageview/inlineToolActivityPresentation.ts';
import { filterArgumentsForCodeDiff } from '@features/chat/message/messageview/inlineToolActivityPayloadParsing.ts';
import { renderInlineToolSection, renderToolActivityQuery, renderToolActivityResult } from '@features/chat/message/messageview/inlineToolActivityPayloadRendering.ts';
import { renderStructuredFields } from '@features/chat/message/messageview/inlineToolFieldRendering.ts';
import { resolveSubagentToolResultModel } from '@features/chat/message/messageview/subagentStreamSegments.ts';
import type { ChatMessageRenderHost, InlineToolActivitySegment, MessageSegment } from '@features/chat/message/messageview/types.ts';
import { resolveInlineActivityDetailsSignature } from '@features/chat/message/messageSegmentSignatures.ts';
import { resolvePayloadRecord } from '@features/chat/toolactivity/payloadReaders.ts';
import { resolveToolOutputTruncation, truncatePlanWriteResultPayload } from '@features/chat/toolactivity/toolOutputPresentation.ts';
import { resolveAssistantVariantIdentity, type AssistantVariantIdentity } from '@core/chat/assistantIdentity.ts';

type TimelineMarkupRenderer = (segments: MessageSegment[]) => string;

const renderInlineToolStatusSummary = (host: ChatMessageRenderHost, segment: InlineToolActivitySegment): string => {
    return `<div class="inline-tool-result-meta inline-tool-status-summary">${host.escapeHtml(resolveInlineToolStatusSummaryText(segment))}</div>`;
};

const omitSubagentOutputFields = (record: JsonObject): JsonObject => {
    const filtered: JsonObject = {};
    for (const [key, value] of Object.entries(record)) {
        if (key === 'result_text' || key === 'output') {
            continue;
        }
        filtered[key] = value;
    }
    return filtered;
};

const formatSubagentDurationLabel = (durationMs: number): string => {
    const safe = Number.isFinite(durationMs) ? Math.max(0, Math.floor(durationMs)) : 0;
    if (safe < 1000) {
        return `${String(safe)}ms`;
    }
    return formatCompactDurationFromMs(safe);
};

const formatEpochMsLabel = (epochMs: number): string => {
    return i18n.formatDate(new Date(epochMs), {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
};

const humanizeSubagentStatusRecord = (record: JsonObject): JsonObject => {
    const source = omitSubagentOutputFields(record);
    const mapped: JsonObject = {};
    for (const [key, value] of Object.entries(source)) {
        if (key === 'duration_ms' && typeof value === 'number' && Number.isFinite(value)) {
            mapped['duration'] = formatSubagentDurationLabel(value);
            continue;
        }
        if (key.endsWith('_at_ms') && typeof value === 'number' && isEpochMsNumber(value)) {
            const nextKey = key.slice(0, Math.max(0, key.length - 3));
            mapped[nextKey] = formatEpochMsLabel(value);
            continue;
        }
        mapped[key] = value;
    }
    return mapped;
};

const renderSubagentStream = (renderTimelineMarkup: TimelineMarkupRenderer, streamSegments: MessageSegment[]): string => {
    if (streamSegments.length === 0) {
        return '';
    }
    return renderTimelineMarkup(streamSegments);
};

const resolveInlineToolAssistantVariantIdentity = (segment: InlineToolActivitySegment): AssistantVariantIdentity | null => {
    return resolveAssistantVariantIdentity({
        assistantTurnTimestamp: segment.assistantTurnAtMs,
        modelVariantIndex: segment.modelVariantIndex
    });
};

const renderRemoveCompactionBoundaryAction = (host: ChatMessageRenderHost, segment: InlineToolActivitySegment, assistantIdentity: AssistantVariantIdentity | null): string => {
    if (segment.status !== 'completed' || assistantIdentity === null || !isManualContextCompactionCallId(segment.callId) || isRemovedContextCompactionResult(segment.result)) {
        return '';
    }
    const label = i18n.t('chat.toolActivity.removeCompactionBoundary');
    const actionAttr = host.escapeAttribute(CHAT_ACTIONS.REMOVE_COMPACTION_BOUNDARY);
    const callIdAttr = host.escapeAttribute(segment.callId);
    const assistantTurnAttr = host.escapeAttribute(String(assistantIdentity.assistantTurnTimestamp));
    const modelVariantAttr = host.escapeAttribute(String(assistantIdentity.modelVariantIndex));
    const disabledAttr = host.isCurrentConversationExecuting() ? ' disabled aria-disabled="true"' : '';
    const button = `<button type="button" class="ui-button ui-button--sm ui-variant-neutral" data-action="${actionAttr}" data-call-id="${callIdAttr}" data-assistant-turn-ts="${assistantTurnAttr}" data-model-variant-index="${modelVariantAttr}" aria-label="${host.escapeAttribute(label)}" data-tooltip="${host.escapeAttribute(label)}"${disabledAttr}>${host.escapeHtml(label)}</button>`;
    return `<div class="inline-tool-detail-actions">${button}</div>`;
};

const renderStopShellAction = (host: ChatMessageRenderHost, segment: InlineToolActivitySegment, assistantIdentity: AssistantVariantIdentity | null): string => {
    if (segment.status !== 'running' || assistantIdentity === null) {
        return '';
    }
    const label = i18n.t('chat.toolActivity.stopShell');
    const actionAttr = host.escapeAttribute(CHAT_ACTIONS.STOP_SHELL);
    const callIdAttr = host.escapeAttribute(segment.callId);
    const assistantTurnAttr = host.escapeAttribute(String(assistantIdentity.assistantTurnTimestamp));
    const modelVariantAttr = host.escapeAttribute(String(assistantIdentity.modelVariantIndex));
    const button = [`<button type="button" class="ui-button ui-button--sm ui-variant-neutral" data-action="${actionAttr}"`, ` data-call-id="${callIdAttr}" data-assistant-turn-ts="${assistantTurnAttr}"`, ` data-model-variant-index="${modelVariantAttr}" aria-label="${host.escapeAttribute(label)}"`, ` data-tooltip="${host.escapeAttribute(label)}">${host.escapeHtml(label)}</button>`].join('');
    return `<div class="inline-tool-detail-actions">${button}</div>`;
};

const renderInlineToolDetails = (host: ChatMessageRenderHost, segment: InlineToolActivitySegment, renderTimelineMarkup: TimelineMarkupRenderer, resolvedPresentation: InlineToolActivityPresentation | null = null, detailsSignature: string = resolveInlineActivityDetailsSignature({ ...segment, collapsed: false }, host.nowMs())): string => {
    const callId = segment.callId;
    const presentation = resolvedPresentation ?? resolveInlineToolActivityPresentation(segment);
    const toolLeafName = presentation.toolLeafName;
    const assistantIdentity = resolveInlineToolAssistantVariantIdentity(segment);
    const isPlanWrite = presentation.isPlanWrite;
    const isSubagentSpawn = presentation.isSubagentSpawn;
    const suppressResult = presentation.suppressResult;
    const codeDiffsHtml = renderInlineToolCodeDiffs(host, segment);

    let argumentsHtml = '';
    if (segment.inputArguments !== undefined && segment.inputArguments !== null) {
        const inputArguments = codeDiffsHtml ? filterArgumentsForCodeDiff(segment.inputArguments) : segment.inputArguments;
        if (inputArguments !== undefined && inputArguments !== null) {
            const queryHtml = renderToolActivityQuery(host, callId, inputArguments);
            if (queryHtml) {
                if (isSubagentSpawn) {
                    const argumentsRecord = resolvePayloadRecord(inputArguments);
                    const taskValue = argumentsRecord ? toTrimmedString(argumentsRecord['task']) : '';
                    const contextValue = argumentsRecord ? toTrimmedString(argumentsRecord['context']) : '';
                    const shouldShowPrompt = taskValue.length > 0 || contextValue.length > 0;
                    if (shouldShowPrompt) {
                        const additionalContextLabel = i18n.t('chat.toolActivity.subagentAdditionalContext');
                        const promptText = contextValue ? `${taskValue}\n\n${additionalContextLabel}\n${contextValue}` : taskValue;
                        const promptFields = renderStructuredFields(host, { prompt: promptText }, { depth: 0, scrollKeyPrefix: callId.trim() ? `tool:${callId.trim()}:subagent:prompt:fields` : null, path: [] });
                        const promptLabel = i18n.t('chat.toolActivity.subagentPrompt');
                        const promptHtml = promptFields ? renderInlineToolSection(host, 'inline-tool-subagent-prompt', promptLabel, promptFields) : '';
                        const remainingArgumentsRecord = argumentsRecord ? Object.fromEntries(Object.entries(argumentsRecord).filter(([key]) => key !== 'task' && key !== 'context')) : null;
                        const remainingQueryHtml = remainingArgumentsRecord && Object.keys(remainingArgumentsRecord).length > 0 ? renderToolActivityQuery(host, callId, remainingArgumentsRecord) : '';
                        argumentsHtml = `<div class="inline-tool-args">${promptHtml}${remainingQueryHtml}</div>`;
                    } else {
                        argumentsHtml = `<div class="inline-tool-args">${queryHtml}</div>`;
                    }
                } else {
                    argumentsHtml = `<div class="inline-tool-args">${queryHtml}</div>`;
                }
            }
        }
    }

    let resultHtml = '';
    const isCompletedOrRunning = segment.status === 'completed' || segment.status === 'running';
    if (!suppressResult && !codeDiffsHtml && segment.result !== undefined && (isCompletedOrRunning || isSubagentSpawn)) {
        const resultPayload = isPlanWrite ? truncatePlanWriteResultPayload(segment.result) : segment.result;
        if (toolLeafName === CONTEXT_COMPACTION_TOOL_LEAF && isCompletedOrRunning) {
            resultHtml = renderContextCompactionToolResult(host, callId, resultPayload) ?? renderToolActivityResult(host, callId, resultPayload, { toolLeafName, requestPayload: segment.inputArguments });
        } else if (!isSubagentSpawn && isCompletedOrRunning) {
            resultHtml = renderToolActivityResult(host, callId, resultPayload, { toolLeafName, requestPayload: segment.inputArguments });
        } else if (isSubagentSpawn) {
            const trimmedCallId = callId.trim();
            try {
                if (assistantIdentity === null) {
                    throw new Error('Subagent tool activity requires assistantTurnTimestamp and modelVariantIndex.');
                }
                const subagentResultPayload: JsonValue = isJsonValue(resultPayload) ? resultPayload : null;
                const { statusRecord, streamSegments } = resolveSubagentToolResultModel(subagentResultPayload, trimmedCallId, {
                    assistantTurnTimestamp: assistantIdentity.assistantTurnTimestamp,
                    modelVariantIndex: assistantIdentity.modelVariantIndex
                });
                const statusFields = renderStructuredFields(host, humanizeSubagentStatusRecord(statusRecord), { depth: 0, scrollKeyPrefix: trimmedCallId ? `tool:${trimmedCallId}:subagent:status:fields` : null, path: [] });
                const statusLabel = i18n.t('chat.toolActivity.subagentStatus');
                const statusHtml = statusFields ? renderInlineToolSection(host, 'inline-tool-subagent-status', statusLabel, statusFields) : '';
                const streamLabel = i18n.t('chat.toolActivity.subagentStream');
                const activityMarkup = renderSubagentStream(renderTimelineMarkup, streamSegments);
                const streamContent = activityMarkup ? `<div class="inline-tool-subagent-stream-timeline">${activityMarkup}</div>` : '';
                const streamHtml = streamContent ? renderInlineToolSection(host, 'inline-tool-subagent-stream', streamLabel, streamContent) : '';
                const resultLabel = i18n.t('chat.toolActivity.result');
                const meta = `<div class="inline-tool-result-meta inline-tool-subagent-result-meta">${statusHtml}${streamHtml}</div>`;
                resultHtml = renderInlineToolSection(host, 'inline-tool-result', resultLabel, meta);
            } catch (error) {
                if (segment.status !== 'error') {
                    throw ensureError(error);
                }
            }
        }
    }

    const boundaryActionHtml = toolLeafName === CONTEXT_COMPACTION_TOOL_LEAF ? renderRemoveCompactionBoundaryAction(host, segment, assistantIdentity) : '';
    const stopShellActionHtml = toolLeafName === 'shell' ? renderStopShellAction(host, segment, assistantIdentity) : '';
    let truncationHtml = '';
    const truncation = segment.result !== undefined ? resolveToolOutputTruncation(segment.result) : null;
    if (truncation !== null) {
        if (assistantIdentity === null) {
            throw new Error('Tool output action requires assistantTurnTimestamp and modelVariantIndex.');
        }
        const viewLabel = i18n.t('chat.toolActivity.viewFullOutput');
        const actionAttr = host.escapeAttribute(CHAT_ACTIONS.OPEN_TOOL_CALL_OUTPUT);
        const callIdAttr = host.escapeAttribute(callId);
        const assistantTurnAttr = host.escapeAttribute(String(assistantIdentity.assistantTurnTimestamp));
        const modelVariantAttr = host.escapeAttribute(String(assistantIdentity.modelVariantIndex));
        const button = `<button type="button" class="ui-button ui-button--sm ui-variant-neutral" data-action="${actionAttr}" data-call-id="${callIdAttr}" data-assistant-turn-ts="${assistantTurnAttr}" data-model-variant-index="${modelVariantAttr}" aria-label="${host.escapeAttribute(viewLabel)}" data-tooltip="${host.escapeAttribute(viewLabel)}">` + `${host.escapeHtml(viewLabel)}` + `</button>`;
        truncationHtml = `<div class="inline-tool-output-truncated">${button}</div>`;
    }

    let errorHtml = '';
    if (segment.status === 'error' && segment.error) {
        const errorLabel = i18n.t('chat.toolActivity.error');
        errorHtml = renderInlineToolSection(host, 'inline-tool-error', errorLabel, ` ${host.escapeHtml(segment.error)}`);
    }
    const statusSummaryHtml = argumentsHtml || codeDiffsHtml || truncationHtml || resultHtml || boundaryActionHtml || stopShellActionHtml || errorHtml ? '' : renderInlineToolStatusSummary(host, segment);

    const detailsKey = callId.trim() ? `tool:${callId.trim()}:details` : '';
    const signatureAttr = ` ${INLINE_ACTIVITY_DETAILS_SIGNATURE_ATTRIBUTE}="${host.escapeAttribute(detailsSignature)}"`;
    const detailsAttr = detailsKey ? ` data-scroll-key="${host.escapeAttribute(detailsKey)}"` : '';
    return `<div class="inline-activity-details"${signatureAttr}${detailsAttr}>${argumentsHtml}${codeDiffsHtml}${truncationHtml}${resultHtml}${boundaryActionHtml}${stopShellActionHtml}${errorHtml}${statusSummaryHtml}</div>`;
};

export { renderInlineToolDetails };
