/* SoAI - Chat feature render call details [frontend/assets/ts/features/chat/message/messageview/renderCallDetails.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { i18n } from '@core/i18n/index.ts';
import { normalizeToolName } from '@features/chat/message/toolActivityPayloadFormatting.ts';
import { renderPayloadStructured } from '@features/chat/message/messageview/inlineToolActivityPayloadRendering.ts';
import type { ChatMessageRenderHost, ToolCallSegment } from '@features/chat/message/messageview/types.ts';
import { injectAssistantBodyRootAttributes } from '@features/chat/message/assistantBodyRootAttributes.ts';

const resolveToolCallArguments = (segment: ToolCallSegment): JsonValue => {
    if (segment.toolArguments !== undefined && segment.toolArguments !== null) {
        return segment.toolArguments;
    }
    if (segment.functionArguments !== undefined && segment.functionArguments !== null) {
        return segment.functionArguments;
    }
    if (segment.input !== undefined && segment.input !== null) {
        return segment.input;
    }
    if (segment.parameters !== undefined && segment.parameters !== null) {
        return segment.parameters;
    }
    return '';
};

const renderToolCallPayload = (host: ChatMessageRenderHost, payload: JsonValue, className: string): string => {
    const structured = renderPayloadStructured(host, payload);
    if (structured) {
        return `<div class="${className}">${structured}</div>`;
    }
    const text = isString(payload) ? payload.trim() : String(payload ?? '');
    if (!text) {
        return '';
    }
    return `<pre class="${className}" data-code-highlighted="true"><code>${host.escapeHtml(text)}</code></pre>`;
};

const renderToolCall = (host: ChatMessageRenderHost, segment: ToolCallSegment): string => {
    let toolName = '';
    if (isString(segment.name) && segment.name.trim()) {
        toolName = segment.name;
    } else if (segment.id !== undefined && segment.id !== null) {
        toolName = String(segment.id);
    } else {
        toolName = i18n.t('chat.message.toolCall');
    }
    toolName = normalizeToolName(toolName);
    const inputArguments = resolveToolCallArguments(segment);
    const argumentsHtml = renderToolCallPayload(host, inputArguments, 'tool-call-args');
    const functionValueHtml = segment.function ? renderToolCallPayload(host, segment.function, 'tool-call-function') : '';
    const metaHtml = segment.metadata ? renderToolCallPayload(host, segment.metadata, 'tool-call-metadata') : '';
    return `<div class="tool-call"><div class="tool-call-header"><span class="tool-call-title">${host.escapeHtml(toolName)}</span></div>${argumentsHtml}${functionValueHtml}${metaHtml}</div>`;
};

const renderMessageError = (host: ChatMessageRenderHost, error: string): string => {
    const icon = host.getIconHtml('warning', { size: 14, strokeWidth: 1.5 });
    const escapedError = host.escapeHtml(error);
    return injectAssistantBodyRootAttributes(host, `<div class="message-error"><span class="message-error-icon">${icon}</span><span class="message-error-text">${escapedError}</span></div>`, 'message_error:1', error);
};

export { renderMessageError, renderToolCall };
