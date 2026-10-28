/* SoAI - Chat feature message action markup [frontend/assets/ts/features/chat/message/messageActionMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { STREAMING_ACTION_CONTROLS_CLASS } from '@features/chat/message/messageActionStreamingPolicy.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatWholeDurationFromMs } from '@core/primitives/duration.ts';
import { isSameDay, resolveLocalCalendarBucket } from '@core/time/localCalendar.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import { resolveStatusPreviewDomStateFromMessage } from '@features/chat/assistanteventtimeline/statusPreviewState.ts';
import { resolveStreamingSpinnerActivityFlags } from '@features/chat/stream/streamMessageSpinnerStatusActivityFlags.ts';
import type { MessageSegment } from '@features/chat/message/messageSegments.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { renderMessageActionButton, renderMessageActionButtons, renderMessageIcon, resolveAssistantActionDefinitions, resolveCompactionBoundaryActionDefinitions, resolveUserActionDefinitions } from '@features/chat/message/messageActionButtons.ts';
import type { MessageActionMarkupContext } from '@features/chat/message/messageActionMarkupTypes.ts';
import type { ChatMessageRenderPresentation } from '@features/chat/message/messageRenderPresentation.ts';
import { renderRunningActivitySummary } from '@features/chat/message/messageRunningActivitySummaryMarkup.ts';
import { STREAM_SPINNER_HAS_PREVIEW_ATTRIBUTE, STREAM_SPINNER_PREVIEW_COOLDOWN_MS_ATTRIBUTE, STREAM_SPINNER_PREVIEW_TEXT_ATTRIBUTE, STREAM_SPINNER_TRIGGER_USER_AT_MS_ATTRIBUTE, STREAM_SPINNER_VISIBLE_ATTRIBUTE } from '@features/chat/stream/streamMessageSpinnerStatusAttributes.ts';

type MessageTimestamp = { label: string; title: string; compactLabel: string; timeLabel: string };

const formatMessageTimestamp = (timestamp: number): MessageTimestamp => {
    if (!isFiniteNumber(timestamp)) {
        throw new Error('Chat message is missing timestamp');
    }
    const date = new Date(timestamp);
    const bucket = resolveLocalCalendarBucket(date, new Date(serverEpochMs()));
    const timeFormat = i18n.formatDate(date, {
        hour: '2-digit',
        minute: '2-digit'
    });
    const todayLabel = i18n.t('chat.message.timestampToday');
    const yesterdayLabel = i18n.t('chat.message.timestampYesterday');
    let label: string;
    if (bucket.type === 'today') {
        label = i18n.t('chat.message.timestampWithTime', { label: todayLabel, time: timeFormat });
    } else if (bucket.type === 'yesterday') {
        label = i18n.t('chat.message.timestampWithTime', { label: yesterdayLabel, time: timeFormat });
    } else {
        label = i18n.formatDate(date, {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    }
    const title = i18n.formatDate(date, {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    return { label, title, compactLabel: i18n.formatDate(date, { year: '2-digit', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }), timeLabel: timeFormat };
};

const formatMessageTimestampRange = (startTimestamp: number, durationMs: number): MessageTimestamp => {
    const start = formatMessageTimestamp(startTimestamp);
    const end = formatMessageTimestamp(startTimestamp + durationMs);
    return {
        label: i18n.t('chat.message.timestampRange', { start: start.label, end: isSameDay(new Date(startTimestamp), new Date(startTimestamp + durationMs)) ? end.timeLabel : end.label }),
        title: i18n.t('chat.message.timestampRange', { start: start.title, end: end.title }),
        compactLabel: end.compactLabel,
        timeLabel: end.timeLabel
    };
};

const renderStreamSpinnerStatus = (): string => {
    const spinnerHtml = '<span class="loading-spinner message-streaming-spinner-indicator" aria-hidden="true"></span>';
    return spinnerHtml + '<span class="message-streaming-status" data-stream-spinner-status="true">' + '<span class="inline-activity-preview-text message-streaming-status-label" data-stream-spinner-text="true">' + '<span class="message-streaming-status-label-text" data-stream-spinner-text-body="true" data-stream-spinner-text-value=""><span class="message-streaming-status-label-text-body" data-stream-spinner-text-body-content="true"></span></span>' + '</span>' + '</span>';
};

const renderAssistantActionLayout = (leftHtml: string, rightHtml: string, streaming: boolean): string => {
    const presenceAttributes = streaming ? '' : ' data-presence-atomic data-presence-visual-only';
    const streamingClass = streaming ? ` ${STREAMING_ACTION_CONTROLS_CLASS}` : '';
    return `<div class="message-action-buttons message-action-buttons--assistant"><div class="message-action-buttons-left${streamingClass}"${presenceAttributes}>${leftHtml}</div><div class="message-action-buttons-right">${rightHtml}</div></div>`;
};

const renderAssistantActionsContainer = (context: MessageActionMarkupContext, message: ChatMessage, inputArguments: { leftButtonsHtml: string; previewText: string; previewCooldownMs: string; triggerUserTimestamp: string; hasPreview: 'true' | 'false'; isStreamingMessage: boolean; segments: readonly MessageSegment[] }): string => {
    const activityAttributes = Object.entries(resolveStreamingSpinnerActivityFlags(inputArguments.segments))
        .map(([name, enabled]) => `${name}="${enabled ? 'true' : 'false'}"`)
        .join(' ');
    const streamSpinnerStatusHtml = renderStreamSpinnerStatus();
    const summaryHtml = renderRunningActivitySummary(context, message);
    const leftHtml = streamSpinnerStatusHtml + inputArguments.leftButtonsHtml + summaryHtml;
    const actionsStateAttribute = inputArguments.isStreamingMessage ? 'true' : 'false';
    return `<div class="message-actions" data-message-streaming="${actionsStateAttribute}" ${STREAM_SPINNER_VISIBLE_ATTRIBUTE}="false" ${STREAM_SPINNER_HAS_PREVIEW_ATTRIBUTE}="${inputArguments.hasPreview}" ${STREAM_SPINNER_PREVIEW_TEXT_ATTRIBUTE}="${inputArguments.previewText}" ${STREAM_SPINNER_PREVIEW_COOLDOWN_MS_ATTRIBUTE}="${inputArguments.previewCooldownMs}" ${STREAM_SPINNER_TRIGGER_USER_AT_MS_ATTRIBUTE}="${inputArguments.triggerUserTimestamp}" ${activityAttributes}>` + `${renderAssistantActionLayout(leftHtml, '', inputArguments.isStreamingMessage)}` + `</div>`;
};

const renderMessageActionLayout = (leftButtonsHtml: string): string => {
    return `<div class="message-action-buttons"><div class="message-action-buttons-left">${leftButtonsHtml}</div><div class="message-action-buttons-right"></div></div>`;
};

const renderTimestampButton = (context: MessageActionMarkupContext, message: ChatMessage, normalizedRole: string, timestamp: MessageTimestamp): string => {
    const copyTimestampLabel = i18n.t('chat.message.actions.copyTimestamp');
    const copyTimestampLabelAttr = context.escapeAttribute(copyTimestampLabel);
    const timing = normalizedRole === 'assistant' ? context.resolveAssistantResponseDuration(message, serverEpochMs()) : null;
    const durationMs = timing?.isSettled === true ? timing.durationFloorMs : null;
    const display = timing?.isSettled === true && timing.completedAtMs !== null ? formatMessageTimestampRange(timing.assistantStartedAtMs, timing.completedAtMs - timing.assistantStartedAtMs) : timestamp;
    const durationHtml = durationMs === null ? '' : `<span class="message-timestamp-duration" aria-hidden="true">${renderMessageIcon(context, 'clock', { size: 14, strokeWidth: 1.7 })}<span class="message-timestamp-duration-text">${context.escapeHtml(formatWholeDurationFromMs(durationMs))}</span></span><span class="message-timestamp-divider" aria-hidden="true">•</span>`;
    const buttonContent = `<span class="message-timestamp-btn-content">${durationHtml}<span class="message-timestamp-text">${context.escapeHtml(display.label)}</span><span class="message-timestamp-text-compact">${context.escapeHtml(display.compactLabel)}</span></span>`;
    return `<button type="button" class="message-action message-timestamp-btn" data-action="copy-timestamp" data-timestamp="${context.escapeAttribute(display.title)}" aria-label="${copyTimestampLabelAttr}" data-tooltip="${context.escapeAttribute(`${copyTimestampLabel} · ${display.title}`)}">${buttonContent}</button>`;
};

type MessageActionRenderPolicy = 'default' | 'invalid_comparison_turn' | 'compaction_boundary';

const renderMessageActions = (context: MessageActionMarkupContext, message: ChatMessage, timestamp: MessageTimestamp, presentation: ChatMessageRenderPresentation, policy: MessageActionRenderPolicy = 'default', options?: { forceSettledAssistantActions?: boolean }, segments: readonly MessageSegment[] = []): string => {
    const currentConversationId = context.getCurrentConversationId();
    const isCurrentConversationExecuting = options?.forceSettledAssistantActions === true ? false : currentConversationId !== null && context.isConversationExecuting(currentConversationId);
    const role = presentation.normalizedRole;
    const timestampBtn = renderTimestampButton(context, message, role, timestamp);
    if (message.messageType === 'control') {
        return `<div class="message-actions">${renderMessageActionLayout(timestampBtn)}</div>`;
    }
    const deleteLabelText = i18n.t('chat.message.actions.delete');
    const deleteBtn = renderMessageActionButton(context, {
        action: 'delete',
        ariaLabel: deleteLabelText,
        className: 'message-action ui-icon-button ui-icon-button-small ui-variant-danger delete-message-btn',
        iconHtml: renderMessageIcon(context, 'close')
    });
    if (role !== 'assistant') {
        const canResendUserMessage = role === 'user' && currentConversationId !== null && !isCurrentConversationExecuting && presentation.canResendUserMessage;
        const resendLabelText = i18n.t('chat.message.actions.resend');
        const resendBtn = canResendUserMessage
            ? renderMessageActionButton(context, {
                  action: 'resend',
                  ariaLabel: resendLabelText,
                  className: 'message-action ui-icon-button ui-icon-button-small ui-variant-neutral resend-message-btn',
                  iconHtml: renderMessageIcon(context, 'send')
              })
            : '';
        const leftButtonsHtml = renderMessageActionButtons(context, resolveUserActionDefinitions()) + resendBtn + deleteBtn + timestampBtn;
        return `<div class="message-actions">${renderMessageActionLayout(leftButtonsHtml)}</div>`;
    }

    if (policy === 'invalid_comparison_turn') {
        const leftButtonsHtml = deleteBtn + timestampBtn;
        return `<div class="message-actions">${renderMessageActionLayout(leftButtonsHtml)}</div>`;
    }
    const previewState = resolveStatusPreviewDomStateFromMessage(message);
    const previewText = previewState.hasPreview ? context.escapeAttribute(previewState.text) : '';
    const previewCooldownMs = previewState.hasPreview ? context.escapeAttribute(String(previewState.cooldownMs)) : '0';
    const hasPreview = previewState.hasPreview ? 'true' : 'false';
    const triggerUserTimestamp = context.escapeAttribute(String(presentation.assistantTriggerUserTimestamp ?? 0));
    const isStreamingMessage =
        options?.forceSettledAssistantActions === true
            ? false
            : (
                  presentation satisfies {
                      readonly isActiveStreamingAssistant: boolean;
                  }
              ).isActiveStreamingAssistant;
    if (policy === 'compaction_boundary') {
        const leftButtonsHtml =
            renderMessageActionButtons(
                context,
                resolveCompactionBoundaryActionDefinitions({
                    regenerateLabel: i18n.t('chat.message.actions.regenerate')
                })
            ) +
            deleteBtn +
            timestampBtn;
        if (isStreamingMessage) return renderAssistantActionsContainer(context, message, { leftButtonsHtml, previewText, previewCooldownMs, triggerUserTimestamp, hasPreview, isStreamingMessage, segments });
        return `<div class="message-actions message-actions--compaction-boundary">${renderAssistantActionLayout(leftButtonsHtml, '', false)}</div>`;
    }

    const totalTokens = message.totalTokens;
    const infoLabel = i18n.t('chat.message.actions.info');
    const copyLabel = i18n.t('chat.message.actions.copy');
    const speakLabel = i18n.t('chat.message.actions.speak');
    const stopSpeakingLabel = i18n.t('chat.message.actions.stopSpeaking');
    const regenerateLabel = i18n.t('chat.message.actions.regenerate');
    const infoTooltipText = isFiniteNumber(totalTokens) ? i18n.t('chat.message.actions.infoTokensTooltip', { tokens: totalTokens }) : infoLabel;
    const leftButtonsHtml =
        renderMessageActionButtons(
            context,
            resolveAssistantActionDefinitions({
                infoTooltipText,
                copyLabel,
                infoLabel,
                speakLabel,
                stopSpeakingLabel,
                regenerateLabel,
                stopIconHtml: renderMessageIcon(context, 'stop', { className: 'ui-icon speak-message-btn-icon speak-message-btn-icon--stop' })
            })
        ) +
        deleteBtn +
        timestampBtn;
    return renderAssistantActionsContainer(context, message, {
        leftButtonsHtml,
        previewText,
        previewCooldownMs,
        triggerUserTimestamp,
        hasPreview,
        isStreamingMessage,
        segments: segments
    });
};

export { formatMessageTimestamp, formatMessageTimestampRange, renderMessageActions };
export type { MessageActionMarkupContext };
