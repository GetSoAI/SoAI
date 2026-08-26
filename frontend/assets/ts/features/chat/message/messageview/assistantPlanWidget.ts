/* SoAI - Chat feature assistant plan widget [frontend/assets/ts/features/chat/message/messageview/assistantPlanWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { CHAT_ACTIONS } from '@features/chat/chatActionIds.ts';
import { renderAssistantActivityWidgetFooter } from '@features/chat/message/messageview/assistantActivityWidgetFooter.ts';
import { stripPreviewReferenceTokensForPlainText } from '@features/chat/message/enhancers/inlineMultimediaPreviewContract.ts';
import { PLAN_WIDGET_ACTION_ICON_OPTIONS, PLAN_WIDGET_HEADER_ICON_OPTIONS } from '@features/chat/message/messageview/assistantPlanWidgetIcons.ts';
import { renderMarkdownContent } from '@features/chat/message/messageview/renderMarkdown.ts';
import { resolveToolResultPlanPayload, type ToolResultPlanPayload } from '@features/chat/message/messageview/toolResultPlanPayload.ts';
import type { ChatMessageRenderHost, InlineToolActivitySegment, MessageSegment } from '@features/chat/message/messageview/types.ts';
import { normalizeToolLeafName } from '@features/chat/toolactivity/toolLeafName.ts';

const PLAN_WRITE_TOOL_NAME = 'plan_write';

interface AssistantPlanWidgetModel {
    payload: ToolResultPlanPayload;
    startedAtMs: number | undefined;
}

const isCompletedPlanWriteSegment = (segment: MessageSegment): segment is InlineToolActivitySegment => {
    return segment.type === 'inline_tool_activity' && segment.status === 'completed' && normalizeToolLeafName(segment.toolName) === PLAN_WRITE_TOOL_NAME;
};

const selectLatestPlanWidgetModel = (segments: readonly MessageSegment[]): AssistantPlanWidgetModel | null => {
    let latest: AssistantPlanWidgetModel | null = null;
    for (const segment of segments) {
        if (!segment || !isCompletedPlanWriteSegment(segment)) {
            continue;
        }
        const payload = resolveToolResultPlanPayload(segment.result);
        if (payload === null) {
            continue;
        }
        latest = { payload, startedAtMs: segment.startedAtMs };
    }
    return latest;
};

const normalizePlanHeadingText = (value: string): string => {
    return value
        .replace(/[#*_`~]/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
        .toLocaleLowerCase();
};

const resolvePlanLeadingLine = (markdown: string): string | null => {
    for (const line of markdown.split('\n')) {
        if (line.trim()) {
            return line;
        }
    }
    return null;
};

const isPlanTitleRepeatedInBody = (title: string, markdown: string): boolean => {
    const leadingLine = resolvePlanLeadingLine(markdown);
    if (leadingLine === null) {
        return false;
    }
    const normalizedTitle = normalizePlanHeadingText(title);
    return normalizedTitle.length > 0 && normalizePlanHeadingText(leadingLine) === normalizedTitle;
};

const renderPlanMetrics = (host: ChatMessageRenderHost, markdown: string): string => {
    const trimmedMarkdown = markdown.trim();
    const metricsLabel = i18n.t('chat.planWidget.metrics', {
        lines: i18n.formatNumber(trimmedMarkdown.split('\n').length),
        characters: i18n.formatNumber(trimmedMarkdown.length)
    });
    return `<span class="assistant-plan-widget__plan-metrics">${host.escapeHtml(metricsLabel)}</span>`;
};

const renderPlanSubtitle = (host: ChatMessageRenderHost, payload: ToolResultPlanPayload): string => {
    if (payload.title === null || isPlanTitleRepeatedInBody(payload.title, payload.markdown)) {
        return renderPlanMetrics(host, payload.markdown);
    }
    return `<span class="assistant-plan-widget__plan-title">${host.escapeHtml(payload.title)}</span>`;
};

const renderPlanScope = (host: ChatMessageRenderHost, payload: ToolResultPlanPayload): string => {
    if (payload.revision === null) {
        return '';
    }
    const revisionLabel = i18n.t('chat.planWidget.revision', { revision: payload.revision });
    return `<span class="assistant-plan-widget__scope">${host.escapeHtml(revisionLabel)}</span>`;
};

const renderPlanHeader = (host: ChatMessageRenderHost, payload: ToolResultPlanPayload): string => {
    const headerIcon = host.getIconHtml('plan', PLAN_WIDGET_HEADER_ICON_OPTIONS);
    const label = host.escapeHtml(i18n.t('chat.planWidget.label'));
    const subtitle = renderPlanSubtitle(host, payload);
    return ['<header class="assistant-plan-widget__header">', '<span class="assistant-plan-widget__title">', `<span class="assistant-plan-widget__title-icon">${headerIcon}</span>`, `<span class="assistant-plan-widget__label">${label}</span>`, subtitle, '</span>', renderPlanScope(host, payload), '</header>'].join('');
};

const renderPlanActionButton = (host: ChatMessageRenderHost, actionId: string, className: string, iconHtml: string, label: string): string => {
    const actionAttribute = host.escapeAttribute(actionId);
    const labelAttribute = host.escapeAttribute(label);
    return `<button type="button" class="${className}" data-action="${actionAttribute}" aria-label="${labelAttribute}" data-tooltip="${labelAttribute}">${iconHtml}<span>${host.escapeHtml(label)}</span></button>`;
};

const renderPlanActions = (host: ChatMessageRenderHost): string => {
    const viewIcon = host.getIconHtml('plan', PLAN_WIDGET_ACTION_ICON_OPTIONS);
    const executeIcon = host.getIconHtml('play', PLAN_WIDGET_ACTION_ICON_OPTIONS);
    const viewButton = renderPlanActionButton(host, CHAT_ACTIONS.VIEW_AGENT_PLAN, 'ui-button ui-button--sm ui-variant-neutral assistant-plan-widget__action', viewIcon, i18n.t('chat.agent.plan.viewPlan'));
    const executeButton = renderPlanActionButton(host, CHAT_ACTIONS.EXECUTE_AGENT_PLAN, 'ui-button ui-button--sm ui-variant-warning assistant-plan-widget__action', executeIcon, i18n.t('chat.planWidget.execute'));
    return `<div class="assistant-plan-widget__actions">${viewButton}${executeButton}</div>`;
};

const resolveDisplayedPlan = (host: ChatMessageRenderHost, snapshot: ToolResultPlanPayload): ToolResultPlanPayload => {
    const canonicalPlan = host.getCanonicalPlan();
    if (canonicalPlan === null || !canonicalPlan.markdown.trim()) {
        return snapshot;
    }
    return { markdown: canonicalPlan.markdown, revision: canonicalPlan.revision, title: canonicalPlan.title };
};

const renderAssistantPlanWidget = (host: ChatMessageRenderHost, segments: readonly MessageSegment[]): string => {
    const model = selectLatestPlanWidgetModel(segments);
    if (model === null) {
        return '';
    }
    const plan = resolveDisplayedPlan(host, model.payload);
    const ariaLabel = host.escapeAttribute(i18n.t('chat.planWidget.label'));
    const bodyHtml = renderMarkdownContent(host, stripPreviewReferenceTokensForPlainText(plan.markdown));
    return [`<section class="assistant-plan-widget" aria-label="${ariaLabel}">`, renderPlanHeader(host, plan), `<div class="assistant-plan-widget__body">${bodyHtml}</div>`, renderPlanActions(host), renderAssistantActivityWidgetFooter(host, model.startedAtMs), '</section>'].join('');
};

export { renderAssistantPlanWidget };
