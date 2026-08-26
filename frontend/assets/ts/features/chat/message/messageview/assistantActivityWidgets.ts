/* SoAI - Chat feature assistant activity widgets [frontend/assets/ts/features/chat/message/messageview/assistantActivityWidgets.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { renderAssistantGeneratedImageWidget } from '@features/chat/message/messageview/assistantGeneratedImageWidget.ts';
import { renderAssistantNewsWidget } from '@features/chat/message/messageview/assistantNewsWidget.ts';
import { renderAssistantPlanWidget } from '@features/chat/message/messageview/assistantPlanWidget.ts';
import { renderAssistantWeatherWidget } from '@features/chat/message/messageview/assistantWeatherWidget.ts';
import { injectAssistantBodyRootAttributes } from '@features/chat/message/assistantBodyRootAttributes.ts';
import { ASSISTANT_ACTIVITY_WIDGETS_ATTRIBUTE } from '@features/chat/message/assistantResponseMarkup.ts';
import { resolveToolResultNewsPayload } from '@features/chat/message/messageview/toolResultNewsPayload.ts';
import { resolveToolResultWeatherPayload } from '@features/chat/message/messageview/toolResultWeatherPayload.ts';
import type { ChatMessageRenderHost, InlineToolActivitySegment, MessageSegment } from '@features/chat/message/messageview/types.ts';
import { buildToolImagePayloadSignature, resolveToolImagePayload } from '@features/chat/toolactivity/toolImagePayload.ts';
import { normalizeToolLeafName } from '@features/chat/toolactivity/toolLeafName.ts';

type AssistantActivityWidgetRenderer = (host: ChatMessageRenderHost, segment: MessageSegment) => string;

const WIDGET_RENDERERS: readonly AssistantActivityWidgetRenderer[] = [renderAssistantGeneratedImageWidget, renderAssistantNewsWidget, renderAssistantWeatherWidget];

const resolveWidgetSlot = (segment: InlineToolActivitySegment): string => {
    const toolLeafName = normalizeToolLeafName(segment.toolName);
    if (toolLeafName === 'weather') {
        const payload = resolveToolResultWeatherPayload(segment.result);
        if (payload !== null) {
            const displayedPayload = { ...payload, current: { ...payload.current, time: '' } };
            return `weather:${JSON.stringify(displayedPayload)}`;
        }
    }
    if (toolLeafName === 'news') {
        const payload = resolveToolResultNewsPayload(segment.result);
        if (payload !== null) {
            return `news:${JSON.stringify(payload)}`;
        }
    }
    if (toolLeafName === 'generate_image') {
        const payload = resolveToolImagePayload(segment.result);
        if (payload !== null) {
            return `generate_image:${buildToolImagePayloadSignature('flat', payload)}`;
        }
    }
    return `call:${segment.callId.trim()}`;
};

const renderWidgetForSegment = (host: ChatMessageRenderHost, segment: MessageSegment): string => {
    for (const renderWidget of WIDGET_RENDERERS) {
        const html = renderWidget(host, segment);
        if (html) {
            return html;
        }
    }
    return '';
};

const renderAssistantActivityWidgets = (host: ChatMessageRenderHost, segments: readonly MessageSegment[]): string => {
    const seenCallIds = new Set<string>();
    const widgetsBySlot = new Map<string, string>();
    for (const segment of segments) {
        if (!segment || segment.type !== 'inline_tool_activity') {
            continue;
        }
        const callId = segment.callId.trim();
        if (!callId || seenCallIds.has(callId)) {
            continue;
        }
        const widgetHtml = renderWidgetForSegment(host, segment);
        if (!widgetHtml) {
            continue;
        }
        seenCallIds.add(callId);
        widgetsBySlot.set(resolveWidgetSlot(segment), widgetHtml);
    }
    const body = [renderAssistantPlanWidget(host, segments), ...widgetsBySlot.values()].join('');
    if (!body) {
        return '';
    }
    return injectAssistantBodyRootAttributes(host, `<div class="assistant-activity-widgets" ${ASSISTANT_ACTIVITY_WIDGETS_ATTRIBUTE}="true">${body}</div>`, 'assistant_activity_widgets:1', body);
};

export { renderAssistantActivityWidgets };
