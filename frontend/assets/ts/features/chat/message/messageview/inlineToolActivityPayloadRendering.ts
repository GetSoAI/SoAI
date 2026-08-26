/* SoAI - Chat feature inline tool activity payload rendering [frontend/assets/ts/features/chat/message/messageview/inlineToolActivityPayloadRendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ansiToHtmlString } from '@core/ansi/htmlString.ts';
import { containsAnsi, formatTerminalControlCharacters } from '@core/ansi/sgrSegments.ts';
import { i18n } from '@core/i18n/index.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { formatToolActivityPayload } from '@features/chat/message/toolActivityPayloadFormatting.ts';
import { renderStructuredFields } from '@features/chat/message/messageview/inlineToolFieldRendering.ts';
import { omitToolResultImageFields, resolveToolResultImageRender } from '@features/chat/message/messageview/toolResultImageRendering.ts';
import { omitReadVideoResultFields, resolveReadVideoResultRender } from '@features/chat/message/messageview/toolResultReadVideoRendering.ts';
import type { ChatMessageRenderHost } from '@features/chat/message/messageview/types.ts';
import { resolvePayloadRecord, tryExtractRecord } from '@features/chat/toolactivity/payloadReaders.ts';
import { resolveToolResultPresentation } from '@features/chat/toolactivity/toolOutputPresentation.ts';

const renderInlineToolSection = (host: ChatMessageRenderHost, className: string, label: string, bodyHtml: string): string => {
    return `<div class="${className}"><span class="inline-tool-label">${host.escapeHtml(label)}:</span>${bodyHtml}</div>`;
};

const renderInlineToolCodeBlock = (host: ChatMessageRenderHost, callId: string, suffix: 'args' | 'result', payloadText: string): string => {
    const trimmedCallId = callId.trim();
    const scrollKey = trimmedCallId ? `tool:${trimmedCallId}:${suffix}` : '';
    const scrollAttr = scrollKey ? ` data-scroll-key="${host.escapeAttribute(scrollKey)}"` : '';
    const codeHtml = containsAnsi(payloadText) ? ansiToHtmlString(payloadText) : host.escapeHtml(formatTerminalControlCharacters(payloadText));
    return `<pre class="inline-tool-field-pre"${scrollAttr} data-code-highlighted="true"><code>${codeHtml}</code></pre>`;
};

const renderPayloadStructured = (host: ChatMessageRenderHost, payload: JsonValue | undefined): string | null => {
    const record = tryExtractRecord(payload);
    return record ? renderStructuredFields(host, record) || null : null;
};

const renderToolActivityQueryRaw = (host: ChatMessageRenderHost, callId: string, payload: JsonValue | undefined): string => {
    const formatted = formatToolActivityPayload(payload);
    const trimmed = formatted.trim();
    if (!trimmed) {
        return '';
    }
    const requestLabel = i18n.t('chat.toolActivity.request');
    return renderInlineToolSection(host, 'inline-tool-query inline-tool-query-raw', requestLabel, renderInlineToolCodeBlock(host, callId, 'args', trimmed));
};

const renderToolActivityQuery = (host: ChatMessageRenderHost, callId: string, payload: JsonValue | undefined): string => {
    const record = resolvePayloadRecord(payload);
    if (!record) {
        return renderToolActivityQueryRaw(host, callId, payload);
    }
    const requestLabel = i18n.t('chat.toolActivity.request');
    const trimmedCallId = callId.trim();
    const fieldsHtml = renderStructuredFields(host, record, {
        depth: 0,
        scrollKeyPrefix: trimmedCallId ? `tool:${trimmedCallId}:args:fields` : null,
        path: []
    });
    if (!fieldsHtml) {
        return '';
    }
    return renderInlineToolSection(host, 'inline-tool-query inline-tool-query-structured', requestLabel, fieldsHtml);
};

const renderToolActivityResult = (host: ChatMessageRenderHost, callId: string, payload: JsonValue | undefined, options: { toolLeafName?: string; requestPayload?: JsonValue | undefined } = {}): string => {
    const resultLabel = i18n.t('chat.toolActivity.result');
    const record = tryExtractRecord(payload);
    if (record) {
        const trimmedCallId = callId.trim();
        const readVideoRender = options.toolLeafName === 'read_video' ? resolveReadVideoResultRender(host, record) : null;
        const videoFilteredRecord = readVideoRender ? omitReadVideoResultFields(record, readVideoRender) : record;
        const imageRender = readVideoRender === null && videoFilteredRecord !== null ? resolveToolResultImageRender(host, videoFilteredRecord, options.toolLeafName === undefined ? {} : { toolLeafName: options.toolLeafName }) : null;
        const imageConsumedKeys = imageRender ? imageRender.consumedKeys : [];
        const imageFilteredRecord = imageRender ? omitToolResultImageFields(videoFilteredRecord, imageConsumedKeys) : videoFilteredRecord;
        const requestRecord = options.requestPayload === undefined || options.requestPayload === null ? null : resolvePayloadRecord(options.requestPayload);
        const presentation = imageFilteredRecord
            ? resolveToolResultPresentation({
                  toolLeafName: options.toolLeafName ?? '',
                  resultRecord: imageFilteredRecord,
                  requestRecord,
                  consumedImageKeys: imageConsumedKeys
              })
            : { displayRecord: null };
        const displayRecord = presentation.displayRecord;
        const sections: string[] = [];
        if (displayRecord) {
            const fieldsHtml = renderStructuredFields(host, displayRecord, {
                depth: 0,
                scrollKeyPrefix: trimmedCallId ? `tool:${trimmedCallId}:result:fields` : null,
                path: []
            });
            if (fieldsHtml) {
                sections.push(`<div class="inline-tool-result-meta">${fieldsHtml}</div>`);
            }
        }
        if (imageRender) {
            sections.unshift(`<div class="inline-tool-result-media">${imageRender.html}</div>`);
        }
        if (readVideoRender) {
            sections.unshift(`<div class="inline-tool-result-media inline-tool-result-media-video">${readVideoRender.html}</div>`);
        }
        if (sections.length > 0) {
            return renderInlineToolSection(host, 'inline-tool-result', resultLabel, sections.join(''));
        }
    }
    const formatted = formatToolActivityPayload(payload);
    const trimmed = formatted.trim();
    if (!trimmed) {
        return '';
    }
    return renderInlineToolSection(host, 'inline-tool-result', resultLabel, renderInlineToolCodeBlock(host, callId, 'result', trimmed));
};

export { renderInlineToolSection, renderPayloadStructured, renderToolActivityQuery, renderToolActivityResult };
