/* SoAI - Context compaction tool result rendering [frontend/assets/ts/features/chat/message/contextcompaction/resultRendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { renderInlineToolSection } from '@features/chat/message/messageview/inlineToolActivityPayloadRendering.ts';
import { renderStructuredFields } from '@features/chat/message/messageview/inlineToolFieldRendering.ts';
import type { ChatMessageRenderHost } from '@features/chat/message/messageview/types.ts';
import { resolveContextCompactionToolResultModel, type ContextCompactionPromptMessage } from '@features/chat/message/contextcompaction/resultModel.ts';

const renderCompactionTextContent = (host: ChatMessageRenderHost, value: string, className: string): string => {
    const trimmed = value.trim();
    if (!trimmed) {
        return '';
    }
    return `<div class="${className}"><p>${host.escapeHtml(trimmed).replace(/\n/g, '<br>')}</p></div>`;
};

const renderExactPromptMessageContent = (host: ChatMessageRenderHost, value: string): string => {
    if (value.length === 0) {
        return '';
    }
    return `<pre class="inline-tool-compaction-prompt-content">${host.escapeHtml(value)}</pre>`;
};

const renderPromptHeader = (host: ChatMessageRenderHost, promptMessage: ContextCompactionPromptMessage): string => {
    const parts = [`<span class="inline-tool-compaction-prompt-role">${host.escapeHtml(promptMessage.role)}</span>`];
    if (promptMessage.name) {
        parts.push(`<span class="inline-tool-compaction-prompt-name">${host.escapeHtml(promptMessage.name)}</span>`);
    }
    return `<div class="inline-tool-compaction-prompt-meta">${parts.join('')}</div>`;
};

const renderContextCompactionToolResult = (host: ChatMessageRenderHost, callId: string, payload: JsonValue | undefined): string | null => {
    const model = resolveContextCompactionToolResultModel(payload);
    if (model === null) {
        return null;
    }

    const trimmedCallId = callId.trim();
    const sections: string[] = [];
    const outputHtml = renderCompactionTextContent(host, model.outputText, 'inline-tool-compaction-output');
    if (outputHtml) {
        sections.push(renderInlineToolSection(host, 'inline-tool-compaction-summary', i18n.t('chat.toolActivity.compactionSummary'), outputHtml));
    }

    if (model.promptMessage) {
        const promptBody = renderPromptHeader(host, model.promptMessage) + renderExactPromptMessageContent(host, model.promptMessage.content);
        sections.push(renderInlineToolSection(host, 'inline-tool-compaction-prompt', i18n.t('chat.toolActivity.compactionPrompt'), promptBody));
    }

    if (model.metadata) {
        const fieldsHtml = renderStructuredFields(host, model.metadata, {
            depth: 0,
            scrollKeyPrefix: trimmedCallId ? `tool:${trimmedCallId}:compaction:fields` : null,
            path: []
        });
        if (fieldsHtml) {
            sections.push(renderInlineToolSection(host, 'inline-tool-compaction-metadata', i18n.t('chat.toolActivity.compactionMetadata'), fieldsHtml));
        }
    }

    if (sections.length === 0) {
        return null;
    }
    return renderInlineToolSection(host, 'inline-tool-result inline-tool-result-compaction', i18n.t('chat.toolActivity.result'), sections.join(''));
};

export { renderContextCompactionToolResult };
