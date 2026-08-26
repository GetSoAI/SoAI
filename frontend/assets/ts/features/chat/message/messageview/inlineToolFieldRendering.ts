/* SoAI - Chat feature inline tool field rendering [frontend/assets/ts/features/chat/message/messageview/inlineToolFieldRendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ansiToHtmlString } from '@core/ansi/htmlString.ts';
import { containsAnsi, formatTerminalControlCharacters } from '@core/ansi/sgrSegments.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { replaceUnderscoresWithSpaces } from '@core/primitives/text.ts';
import { tryParseJsonText } from '@core/serialization/json.ts';
import { isString } from '@core/typeGuards.ts';
import { isJsonArray, isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { resolveStructuredFieldLanguage } from '@features/chat/message/messageview/inlineToolLanguageResolution.ts';
import { renderInlineToolStatusValue } from '@features/chat/message/messageview/inlineToolStatusValueRendering.ts';
import { parseSsePayload } from '@features/chat/toolactivity/ssePayloadParsing.ts';

const FIELD_INLINE_MAX_LENGTH = 120;
const MAX_FIELD_DEPTH = 4;

const formatFieldKey = (key: string): string => replaceUnderscoresWithSpaces(key);

interface ToolFieldRenderHost {
    escapeHtml: (unsafe: string) => string;
    escapeAttribute: (value: string) => string;
}

type StructuredFieldScrollContext = {
    depth: number;
    record: JsonObject;
    scrollKeyPrefix: string | null;
    path: string[];
};

const encodeScrollKeySegment = (segment: string): string => {
    const normalized = segment.trim();
    if (!normalized) {
        return 'empty';
    }
    return encodeURIComponent(normalized);
};

const buildFieldScrollKey = (context: StructuredFieldScrollContext): string | null => {
    if (!context.scrollKeyPrefix) {
        return null;
    }
    if (context.path.length === 0) {
        return context.scrollKeyPrefix;
    }
    const encoded = context.path.map(encodeScrollKeySegment).join('/');
    return `${context.scrollKeyPrefix}:${encoded}`;
};

const stringifyPrimitive = (value: JsonValue | undefined): string => {
    if (value === null || value === undefined) {
        return 'null';
    }
    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean' || typeof value === 'bigint') {
        return String(value);
    }
    if (typeof value === 'object') {
        try {
            return JSON.stringify(value);
        } catch (error) {
            throw new Error('Tool activity payload contains an unserializable value.', { cause: ensureError(error) });
        }
    }
    return String(value);
};

const FORCE_BLOCK_FIELD_KEYS: ReadonlySet<string> = new Set<string>(['matches', 'output', 'result_text']);
const STABLE_PLAINTEXT_FIELD_KEYS: ReadonlySet<string> = new Set<string>(['content', 'description', 'final_url', 'matches', 'output', 'result_text', 'snippet', 'source', 'title', 'url']);

const renderFieldPre = (host: ToolFieldRenderHost, value: string, scrollKey: string | null, language: string | null, stablePlaintext: boolean): string => {
    const scrollAttr = scrollKey ? ` data-scroll-key="${host.escapeAttribute(scrollKey)}"` : '';
    if (containsAnsi(value)) {
        return `<pre class="inline-tool-field-pre" data-code-highlighted="true"${scrollAttr}><code>${ansiToHtmlString(value)}</code></pre>`;
    }
    const languageAttr = language ? ` data-language="${host.escapeAttribute(language)}"` : '';
    const highlightedAttr = stablePlaintext ? ' data-code-highlighted="true"' : '';
    return `<pre class="inline-tool-field-pre"${highlightedAttr}${languageAttr}${scrollAttr}><code>${host.escapeHtml(formatTerminalControlCharacters(value))}</code></pre>`;
};

const isFieldInlineValue = (key: string, value: JsonValue | undefined): boolean => {
    if (value === null || value === undefined || typeof value === 'boolean' || typeof value === 'number') {
        return true;
    }
    if (isString(value)) {
        if (FORCE_BLOCK_FIELD_KEYS.has(key)) {
            return false;
        }
        return value.length <= FIELD_INLINE_MAX_LENGTH && !value.includes('\n');
    }
    if (isJsonArray(value)) {
        return false;
    }
    return false;
};

const renderFieldInlineValue = (host: ToolFieldRenderHost, key: string, value: JsonValue | undefined): string => {
    const statusValueHtml = renderInlineToolStatusValue(host, key, value);
    if (statusValueHtml !== null) {
        return statusValueHtml;
    }
    if (value === null || value === undefined) {
        return '<span class="inline-tool-field-value inline-tool-field-value-null">null</span>';
    }
    if (typeof value === 'boolean') {
        return `<span class="inline-tool-field-value inline-tool-field-value-bool">${host.escapeHtml(String(value))}</span>`;
    }
    if (typeof value === 'number') {
        return `<span class="inline-tool-field-value inline-tool-field-value-number">${host.escapeHtml(String(value))}</span>`;
    }
    if (isJsonArray(value)) {
        const segments: string[] = [];
        for (const entry of value) {
            segments.push(isString(entry) ? entry : stringifyPrimitive(entry));
        }
        return `<span class="inline-tool-field-value">${host.escapeHtml(segments.join(', '))}</span>`;
    }
    return `<span class="inline-tool-field-value">${host.escapeHtml(isString(value) ? value : String(value))}</span>`;
};

const renderArrayBlockValue = (host: ToolFieldRenderHost, value: readonly JsonValue[], context: StructuredFieldScrollContext): string => {
    const items: string[] = [];
    for (let index = 0; index < value.length; index += 1) {
        const entry = value[index];
        if (isJsonObject(entry)) {
            const subFields = renderStructuredFields(host, entry, {
                depth: context.depth + 1,
                scrollKeyPrefix: context.scrollKeyPrefix,
                path: context.path.concat([`[${String(index)}]`])
            });
            if (subFields) {
                items.push(`<div class="inline-tool-field-list-item">${subFields}</div>`);
                continue;
            }
        }
        const text = isString(entry) ? entry : stringifyPrimitive(entry);
        items.push(`<div class="inline-tool-field-list-item"><span class="inline-tool-field-value">${host.escapeHtml(text)}</span></div>`);
    }
    if (items.length === 0) {
        return '';
    }
    return `<div class="inline-tool-field-list">${items.join('')}</div>`;
};

const renderFieldBlockValue = (host: ToolFieldRenderHost, value: JsonValue | undefined, context: StructuredFieldScrollContext, language: string | null = null, stablePlaintext: boolean = false): string => {
    if (isString(value)) {
        let displayValue = value;
        const trimmed = value.trim();

        const sseParsed = parseSsePayload(trimmed);
        if (sseParsed !== null) {
            displayValue = JSON.stringify(sseParsed, null, 2);
        } else if ((trimmed.startsWith('{') && trimmed.endsWith('}')) || (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
            const parsed = tryParseJsonText(trimmed);
            if (isJsonObject(parsed) || isJsonArray(parsed)) {
                displayValue = JSON.stringify(parsed, null, 2);
            }
        }
        const scrollKey = buildFieldScrollKey(context);
        return renderFieldPre(host, displayValue, scrollKey, language, stablePlaintext);
    }
    if (isJsonObject(value)) {
        return renderStructuredFields(host, value, {
            depth: context.depth + 1,
            scrollKeyPrefix: context.scrollKeyPrefix,
            path: context.path
        });
    }
    if (isJsonArray(value)) {
        return renderArrayBlockValue(host, value, context);
    }
    const scrollKey = buildFieldScrollKey(context);
    return renderFieldPre(host, String(value ?? ''), scrollKey, language, stablePlaintext);
};

const renderFieldRow = (host: ToolFieldRenderHost, key: string, value: JsonValue | undefined, context: StructuredFieldScrollContext): string => {
    const label = formatFieldKey(key);
    const escapedLabel = host.escapeHtml(`${label}:`);
    const fieldLanguage = resolveStructuredFieldLanguage(key, value, context.record);
    if (context.depth >= MAX_FIELD_DEPTH) {
        if (isJsonObject(value) || isJsonArray(value)) {
            let displayValue = '';
            try {
                displayValue = JSON.stringify(value, null, 2);
            } catch (error) {
                throw new Error('Tool activity payload contains an unserializable value.', { cause: ensureError(error) });
            }
            const scrollKey = buildFieldScrollKey({
                ...context,
                path: context.path.concat([key])
            });
            const pre = renderFieldPre(host, displayValue, scrollKey, fieldLanguage, STABLE_PLAINTEXT_FIELD_KEYS.has(key) && fieldLanguage === null);
            return `<div class="inline-tool-field inline-tool-field-block"><span class="inline-tool-field-key">${escapedLabel}</span> ${pre}</div>`;
        }
        const text = isString(value) ? value : stringifyPrimitive(value);
        const statusValueHtml = renderInlineToolStatusValue(host, key, value);
        const valueHtml = statusValueHtml ?? `<span class="inline-tool-field-value">${host.escapeHtml(text)}</span>`;
        return `<div class="inline-tool-field"><span class="inline-tool-field-key">${escapedLabel}</span> ${valueHtml}</div>`;
    }
    if (isFieldInlineValue(key, value)) {
        const valueHtml = renderFieldInlineValue(host, key, value);
        return `<div class="inline-tool-field"><span class="inline-tool-field-key">${escapedLabel}</span> ${valueHtml}</div>`;
    }
    const valueHtml = renderFieldBlockValue(
        host,
        value,
        {
            ...context,
            path: context.path.concat([key])
        },
        fieldLanguage,
        STABLE_PLAINTEXT_FIELD_KEYS.has(key) && fieldLanguage === null
    );
    return `<div class="inline-tool-field inline-tool-field-block"><span class="inline-tool-field-key">${escapedLabel}</span> ${valueHtml}</div>`;
};

const renderStructuredFields = (host: ToolFieldRenderHost, record: JsonObject, options: { depth: number; scrollKeyPrefix: string | null; path: string[] } = { depth: 0, scrollKeyPrefix: null, path: [] }): string => {
    const entries = Object.entries(record);
    if (entries.length === 0) {
        return '';
    }
    const rows: string[] = [];
    for (const [key, value] of entries) {
        rows.push(
            renderFieldRow(host, key, value, {
                depth: options.depth,
                record,
                scrollKeyPrefix: options.scrollKeyPrefix,
                path: options.path
            })
        );
    }
    return `<div class="inline-tool-fields">${rows.join('')}</div>`;
};

export { renderStructuredFields };
