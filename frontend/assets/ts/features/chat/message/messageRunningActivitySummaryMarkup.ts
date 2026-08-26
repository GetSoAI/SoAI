/* SoAI - Assistant message running activity summary markup [frontend/assets/ts/features/chat/message/messageRunningActivitySummaryMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { getTooltipText, setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { CHAT_ACTIONS } from '@features/chat/chatActionIds.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { hasTerminalAssistantState } from '@features/chat/message/assistantTerminalState.ts';
import type { MessageActionMarkupContext } from '@features/chat/message/messageActionMarkupTypes.ts';
import { formatBackgroundActivitySummaryText, formatRunningActivitySummaryText, type RunningActivitySummary } from '@features/chat/toolactivity/runningActivitySummary.ts';

const RUNNING_ACTIVITY_SUMMARY_ATTRIBUTE = 'data-running-activity-summary';
const RUNNING_ACTIVITY_SUMMARY_TEXT_ATTRIBUTE = 'data-running-activity-summary-text';
const RUNNING_ACTIVITY_SUMMARY_VISIBLE_ATTRIBUTE = 'data-running-activity-summary-visible';
const RUNNING_ACTIVITY_REVEAL_PENDING_ATTRIBUTE = 'data-running-activity-reveal-pending';
const RUNNING_ACTIVITY_SUMMARY_LABEL_SELECTOR = '.message-running-activity-summary-label';
const RUNNING_ACTIVITY_SUMMARY_SELECTOR = '.message-running-activity-summary';

const resolveSnapshotSummaryText = (context: MessageActionMarkupContext, message: ChatMessage): string | null => {
    const snapshot = context.getCurrentRunningActivitySnapshot();
    const terminal = hasTerminalAssistantState(message);
    const target = terminal ? (snapshot?.backgroundTarget ?? null) : (snapshot?.target ?? null);
    if (snapshot === null || target === null) {
        return null;
    }
    if (message.assistantTurnAtMs !== target.assistantTurnAtMs || message.modelVariantIndex !== target.modelVariantIndex) {
        return null;
    }
    const activityCount = terminal ? snapshot.backgroundActivityCount : snapshot.activityCount;
    const subagentCount = terminal ? snapshot.backgroundSubagentCount : snapshot.subagentCount;
    if (activityCount <= 0 && subagentCount <= 0) {
        return null;
    }
    return terminal ? formatBackgroundActivitySummaryText(activityCount, subagentCount) : formatRunningActivitySummaryText(activityCount, subagentCount);
};

const renderRunningActivitySummary = (context: MessageActionMarkupContext, message: ChatMessage): string => {
    const summary = context.resolveRunningActivitySummaryForMarkup(message, serverEpochMs());
    const text = summary.text || resolveSnapshotSummaryText(context, message) || '';
    const visible = text ? 'true' : 'false';
    const escapedText = context.escapeHtml(text);
    const escapedTextAttr = context.escapeAttribute(text);
    return `<span class="message-running-activity-summary" ${RUNNING_ACTIVITY_SUMMARY_ATTRIBUTE}="true" ${RUNNING_ACTIVITY_SUMMARY_VISIBLE_ATTRIBUTE}="${visible}" ${RUNNING_ACTIVITY_SUMMARY_TEXT_ATTRIBUTE}="${escapedTextAttr}"><button type="button" class="message-running-activity-summary-text" data-action="${context.escapeAttribute(CHAT_ACTIONS.REVEAL_RUNNING_ACTIVITY)}" aria-label="${escapedTextAttr}" data-tooltip="${escapedTextAttr}"><span class="message-running-activity-summary-label">${escapedText}</span><span class="loading-spinner message-running-activity-summary-reveal-spinner" aria-hidden="true"></span></button></span>`;
};

const syncRunningActivitySummaryElement = (summaryElement: HTMLElement, summary: RunningActivitySummary): boolean => {
    const visible = summary.text ? 'true' : 'false';
    let changed = false;
    if (summaryElement.getAttribute(RUNNING_ACTIVITY_SUMMARY_VISIBLE_ATTRIBUTE) !== visible) {
        summaryElement.setAttribute(RUNNING_ACTIVITY_SUMMARY_VISIBLE_ATTRIBUTE, visible);
        changed = true;
    }
    if (summaryElement.getAttribute(RUNNING_ACTIVITY_SUMMARY_TEXT_ATTRIBUTE) !== summary.text) {
        summaryElement.setAttribute(RUNNING_ACTIVITY_SUMMARY_TEXT_ATTRIBUTE, summary.text);
        changed = true;
    }
    const text = dom.resolve('.message-running-activity-summary-text', summaryElement);
    if (!(text instanceof HTMLButtonElement)) {
        throw new Error('Assistant running activity summary is missing text button.');
    }
    const label = dom.resolve(RUNNING_ACTIVITY_SUMMARY_LABEL_SELECTOR, text);
    if (!(label instanceof HTMLElement)) {
        throw new Error('Assistant running activity summary is missing text label.');
    }
    if (label.textContent !== summary.text) {
        label.textContent = summary.text;
        changed = true;
    }
    if (text.getAttribute('aria-label') !== summary.text) {
        text.setAttribute('aria-label', summary.text);
        changed = true;
    }
    const tooltipText = summary.text || null;
    if (getTooltipText(text) !== tooltipText) {
        setTooltipText(text, summary.text);
        changed = true;
    }
    return changed;
};

const setRunningActivityRevealPending = (actionElement: HTMLElement | null | undefined, pending: boolean): void => {
    const summaryElement = actionElement?.closest(RUNNING_ACTIVITY_SUMMARY_SELECTOR);
    if (!(summaryElement instanceof HTMLElement)) {
        return;
    }
    if (pending) {
        summaryElement.setAttribute(RUNNING_ACTIVITY_REVEAL_PENDING_ATTRIBUTE, 'true');
        return;
    }
    summaryElement.removeAttribute(RUNNING_ACTIVITY_REVEAL_PENDING_ATTRIBUTE);
};

export { RUNNING_ACTIVITY_SUMMARY_ATTRIBUTE, RUNNING_ACTIVITY_SUMMARY_TEXT_ATTRIBUTE, RUNNING_ACTIVITY_SUMMARY_VISIBLE_ATTRIBUTE, renderRunningActivitySummary, setRunningActivityRevealPending, syncRunningActivitySummaryElement };
