/* SoAI - Chat feature message action markup [frontend/assets/ts/features/chat/message/messageActionMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatWholeDurationFromMs } from '@core/primitives/duration.ts';
import { resolveLocalCalendarBucket } from '@core/time/localCalendar.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import { resolveStatusPreviewDomStateFromMessage } from '@features/chat/assistanteventtimeline/statusPreviewState.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { resolveAssistantSettledResponseDisplayDurationMs } from '@features/chat/message/assistantResponseDuration.ts';
import { renderMessageActionButton, renderMessageActionButtons, renderMessageIcon, resolveAssistantActionDefinitions, resolveCompactionBoundaryActionDefinitions, resolveUserActionDefinitions } from '@features/chat/message/messageActionButtons.ts';
import type { MessageActionMarkupContext } from '@features/chat/message/messageActionMarkupTypes.ts';
import type { ChatMessageRenderPresentation } from '@features/chat/message/messageRenderPresentation.ts';
import { renderRunningActivitySummary } from '@features/chat/message/messageRunningActivitySummaryMarkup.ts';
import { STREAM_SPINNER_HAS_LOADING_ACTIVITY_ATTRIBUTE, STREAM_SPINNER_HAS_PREVIEW_ATTRIBUTE, STREAM_SPINNER_HAS_RUNNING_CONTEXT_COMPACTION_ACTIVITY_ATTRIBUTE, STREAM_SPINNER_HAS_RUNNING_LOADING_ACTIVITY_ATTRIBUTE, STREAM_SPINNER_HAS_RUNNING_WAIT_ACTIVITY_ATTRIBUTE, STREAM_SPINNER_PREVIEW_COOLDOWN_MS_ATTRIBUTE, STREAM_SPINNER_PREVIEW_TEXT_ATTRIBUTE, STREAM_SPINNER_TRIGGER_USER_AT_MS_ATTRIBUTE, STREAM_SPINNER_VISIBLE_ATTRIBUTE } from '@features/chat/stream/streamMessageSpinnerStatusAttributes.ts';

const formatMessageTimestamp = (timestamp: number): { label: string; title: string } => {
    if (!isFiniteNumber(timestamp)) {
        throw new Error('Chat message is missing timestamp');
    }
    const date = new Date(timestamp);
    const bucket = resolveLocalCalendarBucket(date, new Date(serverEpochMs()), { futureAsToday: true });
    const timeFormat = i18n.formatDate(date, {
        hour: '2-digit',
        minute: '2-digit'
    });
    const todayLabel = i18n.t('chat.message.timestampToday');
    const yesterdayLabel = i18n.t('chat.message.timestampYesterday');
    let label: string;
    if (bucket.type === 'today') {
        label = `${todayLabel}, ${timeFormat}`;
    } else if (bucket.type === 'yesterday') {
        label = `${yesterdayLabel}, ${timeFormat}`;
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
    return { label, title };
};

const formatMessageTimestampRange = (startTimestamp: number, durationMs: number): { label: string; title: string } => {
    const start = formatMessageTimestamp(startTimestamp);
    const end = formatMessageTimestamp(startTimestamp + durationMs);
    return {
        label: i18n.t('chat.message.timestampRange', { start: start.label, end: end.label }),
        title: i18n.t('chat.message.timestampRange', { start: start.title, end: end.title })
    };
};

const renderStreamSpinnerStatus = (): string => {
    const spinnerHtml = '<span class="loading-spinner message-streaming-spinner-indicator" aria-hidden="true"></span>';
    return spinnerHtml + '<span class="message-streaming-status" data-stream-spinner-status="true">' + '<span class="inline-activity-preview-text message-streaming-status-label" data-stream-spinner-text="true">' + '<span class="message-streaming-status-label-text" data-stream-spinner-text-body="true" data-stream-spinner-text-value=""><span class="message-streaming-status-label-text-body" data-stream-spinner-text-body-content="true"></span></span>' + '</span>' + '</span>';
};

const renderAssistantActionButtons = (leftButtonsHtml: string, isStreamingMessage: boolean): string => {
    if (isStreamingMessage) {
        return '';
    }
    return leftButtonsHtml;
};

const renderAssistantActionLayout = (leftHtml: string, rightHtml: string): string => {
    return `<div class="message-action-buttons message-action-buttons--assistant"><div class="message-action-buttons-left">${leftHtml}</div><div class="message-action-buttons-right">${rightHtml}</div></div>`;
};

const renderAssistantActionsContainer = (context: MessageActionMarkupContext, message: ChatMessage, inputArguments: { leftButtonsHtml: string; previewText: string; previewCooldownMs: string; triggerUserTimestamp: string; hasPreview: 'true' | 'false'; isStreamingMessage: boolean }): string => {
    const streamSpinnerStatusHtml = renderStreamSpinnerStatus();
    const summaryHtml = renderRunningActivitySummary(context, message);
    const leftHtml = streamSpinnerStatusHtml + renderAssistantActionButtons(inputArguments.leftButtonsHtml, inputArguments.isStreamingMessage) + summaryHtml;
    const actionsStateAttribute = inputArguments.isStreamingMessage ? 'true' : 'false';
    return `<div class="message-actions" data-message-streaming="${actionsStateAttribute}" ${STREAM_SPINNER_VISIBLE_ATTRIBUTE}="false" ${STREAM_SPINNER_HAS_PREVIEW_ATTRIBUTE}="${inputArguments.hasPreview}" ${STREAM_SPINNER_PREVIEW_TEXT_ATTRIBUTE}="${inputArguments.previewText}" ${STREAM_SPINNER_PREVIEW_COOLDOWN_MS_ATTRIBUTE}="${inputArguments.previewCooldownMs}" ${STREAM_SPINNER_TRIGGER_USER_AT_MS_ATTRIBUTE}="${inputArguments.triggerUserTimestamp}" ${STREAM_SPINNER_HAS_LOADING_ACTIVITY_ATTRIBUTE}="false" ${STREAM_SPINNER_HAS_RUNNING_LOADING_ACTIVITY_ATTRIBUTE}="false" ${STREAM_SPINNER_HAS_RUNNING_WAIT_ACTIVITY_ATTRIBUTE}="false" ${STREAM_SPINNER_HAS_RUNNING_CONTEXT_COMPACTION_ACTIVITY_ATTRIBUTE}="false">` + `${renderAssistantActionLayout(leftHtml, '')}` + `</div>`;
};

const renderStreamingAssistantActionsContainer = (context: MessageActionMarkupContext, message: ChatMessage, inputArguments: { previewText: string; previewCooldownMs: string; triggerUserTimestamp: string; hasPreview: 'true' | 'false' }): string => {
    return renderAssistantActionsContainer(context, message, {
        leftButtonsHtml: '',
        previewText: inputArguments.previewText,
        previewCooldownMs: inputArguments.previewCooldownMs,
        triggerUserTimestamp: inputArguments.triggerUserTimestamp,
        hasPreview: inputArguments.hasPreview,
        isStreamingMessage: true
    });
};

const resolveMessageDurationMs = (message: ChatMessage, normalizedRole: string): number | null => {
    if (normalizedRole === 'assistant') {
        return resolveAssistantSettledResponseDisplayDurationMs(message, serverEpochMs());
    }
    return null;
};

const renderMessageActionLayout = (leftButtonsHtml: string): string => {
    return `<div class="message-action-buttons"><div class="message-action-buttons-left">${leftButtonsHtml}</div><div class="message-action-buttons-right"></div></div>`;
};

const renderTimestampButton = (context: MessageActionMarkupContext, message: ChatMessage, normalizedRole: string, timestamp: { label: string; title: string }): string => {
    const copyTimestampLabel = i18n.t('chat.message.actions.copyTimestamp');
    const copyTimestampLabelAttr = context.escapeAttribute(copyTimestampLabel);
    const durationMs = resolveMessageDurationMs(message, normalizedRole);
    if (durationMs === null || !isFiniteNumber(message.timestamp)) {
        return `<button type="button" class="message-action message-timestamp-btn" data-action="copy-timestamp" data-timestamp="${context.escapeAttribute(timestamp.title)}" aria-label="${copyTimestampLabelAttr}" data-tooltip="${copyTimestampLabelAttr}">${context.escapeHtml(timestamp.label)}</button>`;
    }
    const timestampRange = formatMessageTimestampRange(message.timestamp, durationMs);
    const durationLabel = formatWholeDurationFromMs(durationMs);
    const clockIcon = renderMessageIcon(context, 'clock', { size: 14, strokeWidth: 1.7 });
    const buttonContent = `<span class="message-timestamp-btn-content"><span class="message-timestamp-duration" aria-hidden="true">${clockIcon}<span class="message-timestamp-duration-text">${context.escapeHtml(durationLabel)}</span></span><span class="message-timestamp-divider" aria-hidden="true">•</span><span class="message-timestamp-text">${context.escapeHtml(timestampRange.label)}</span></span>`;
    return `<button type="button" class="message-action message-timestamp-btn" data-action="copy-timestamp" data-timestamp="${context.escapeAttribute(timestampRange.title)}" aria-label="${copyTimestampLabelAttr}" data-tooltip="${copyTimestampLabelAttr}">${buttonContent}</button>`;
};

type MessageActionRenderPolicy = 'default' | 'invalid_comparison_turn' | 'compaction_boundary';

const renderMessageActions = (context: MessageActionMarkupContext, message: ChatMessage, timestamp: { label: string; title: string }, presentation: ChatMessageRenderPresentation, policy: MessageActionRenderPolicy = 'default', options?: { forceSettledAssistantActions?: boolean }): string => {
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
        if (isStreamingMessage) {
            return renderStreamingAssistantActionsContainer(context, message, { previewText, previewCooldownMs, triggerUserTimestamp, hasPreview });
        }
        const leftButtonsHtml =
            renderMessageActionButtons(
                context,
                resolveCompactionBoundaryActionDefinitions({
                    regenerateLabel: i18n.t('chat.message.actions.regenerate')
                })
            ) +
            deleteBtn +
            timestampBtn;
        return `<div class="message-actions message-actions--compaction-boundary">${renderMessageActionLayout(leftButtonsHtml)}</div>`;
    }

    if (isStreamingMessage) {
        return renderStreamingAssistantActionsContainer(context, message, { previewText, previewCooldownMs, triggerUserTimestamp, hasPreview });
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
        isStreamingMessage: false
    });
};

export { formatMessageTimestamp, formatMessageTimestampRange, renderMessageActions };
export type { MessageActionMarkupContext };
