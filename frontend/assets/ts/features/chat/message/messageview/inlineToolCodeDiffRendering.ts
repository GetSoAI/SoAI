/* SoAI - Renders inline code diff entries for tool activity segments [frontend/assets/ts/features/chat/message/messageview/inlineToolCodeDiffRendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { isArray, isString } from '@core/typeGuards.ts';
import { i18n } from '@core/i18n/index.ts';
import { resolveToolResultCodeDiffs } from '@features/chat/message/toolActivityCodeDiffs.ts';
import { renderMarkdownContent } from '@features/chat/message/messageview/renderMarkdown.ts';
import type { ChatMessageRenderHost, InlineToolActivitySegment } from '@features/chat/message/messageview/types.ts';

const sanitizeFenceBreakers = (value: string): string => value.replace(/```/g, '``\\`');

const addScrollKeyToFirstPre = (html: string, scrollKey: string, escapeAttribute: (value: string) => string): string => {
    const trimmed = String(html || '').trim();
    if (!trimmed) {
        return trimmed;
    }
    const start = trimmed.indexOf('<pre');
    if (start < 0) {
        return trimmed;
    }
    const end = trimmed.indexOf('>', start);
    if (end < 0) {
        return trimmed;
    }
    const openingTag = trimmed.slice(start, end);
    if (openingTag.includes('data-scroll-key=')) {
        return trimmed;
    }
    const escapedKey = escapeAttribute(scrollKey);
    return `${trimmed.slice(0, end)} data-scroll-key="${escapedKey}"${trimmed.slice(end)}`;
};

const renderInlineToolCodeDiffs = (host: ChatMessageRenderHost, segment: InlineToolActivitySegment): string => {
    const resolvedCodeDiffs = isArray(segment.codeDiffs) && segment.codeDiffs.length > 0 ? segment.codeDiffs : resolveToolResultCodeDiffs(segment.result);
    if (!isArray(resolvedCodeDiffs) || resolvedCodeDiffs.length === 0) {
        return '';
    }

    const renderedEntries: string[] = [];
    let viewedEntryCount = 0;
    for (const [index, codeDiff] of resolvedCodeDiffs.entries()) {
        if (!codeDiff || !isString(codeDiff.diff)) {
            continue;
        }
        const diffValue = codeDiff.diff.replace(/\r\n/g, '\n').trim();
        if (!diffValue) {
            continue;
        }
        const fencedDiffMarkdown = `\`\`\`diff\n${sanitizeFenceBreakers(diffValue)}\n\`\`\``;
        const diffMarkdownHtml = renderMarkdownContent(host, fencedDiffMarkdown);
        const callId = segment.callId.trim();
        const scrollKey = callId ? `tool:${callId}:diff:${String(index + 1)}` : '';
        const stabilizedHtml = scrollKey ? addScrollKeyToFirstPre(diffMarkdownHtml, scrollKey, host.escapeAttribute) : diffMarkdownHtml;
        const pathValue = toTrimmedString(codeDiff.path);
        const pathHtml = pathValue ? `<span class="inline-tool-code-diff-path">${host.escapeHtml(pathValue)}</span>` : '';
        const isViewed = codeDiff.operation === 'viewed';
        if (isViewed) {
            viewedEntryCount += 1;
        }
        const truncatedLabel = isViewed ? i18n.t('chat.toolActivity.fileViewPartial') : i18n.t('chat.toolActivity.diffTruncated');
        const truncatedHtml = codeDiff.truncated === true ? `<span class="inline-tool-code-diff-truncated">${host.escapeHtml(truncatedLabel)}</span>` : '';
        renderedEntries.push(`<div class="inline-tool-code-diff-entry">${pathHtml}${truncatedHtml}${stabilizedHtml}</div>`);
    }

    if (renderedEntries.length === 0) {
        return '';
    }
    const codeDiffLabel = viewedEntryCount === renderedEntries.length ? i18n.t('chat.toolActivity.fileView') : i18n.t('chat.toolActivity.codeDiff');
    return `<div class="inline-tool-code-diffs"><span class="inline-tool-label">${host.escapeHtml(codeDiffLabel)}:</span>${renderedEntries.join('')}</div>`;
};

export { renderInlineToolCodeDiffs };
