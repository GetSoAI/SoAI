/* SoAI - Shared rich text renderer mappers [frontend/assets/ts/core/richtextrenderer/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { FootnoteDefinition, FootnoteProcessResult, RenderBlock } from '@core/richtextrenderer/types.ts';
import { createFencedCodeBlockPattern } from '@core/richtextrenderer/richTextBlockSyntax.ts';

export const normalizeMultilineInput = (content: string): string => {
    return String(content ?? '').replace(/\r\n?/g, '\n');
};

export const buildRenderBlocks = (content: string, normalizeLanguageHintWithAlias: (rawLanguageHint: string | undefined | null) => string | null): RenderBlock[] => {
    const blocks: RenderBlock[] = [];
    const pattern = createFencedCodeBlockPattern();
    let lastIndex = 0;
    let match: RegExpExecArray | null;
    while ((match = pattern.exec(content)) !== null) {
        if (match.index > lastIndex) {
            blocks.push({ type: 'text', value: content.slice(lastIndex, match.index) });
        }
        const language = normalizeLanguageHintWithAlias(match[1]);
        const rawCode = match[2] ?? '';
        blocks.push({ type: 'code', value: rawCode, language });
        lastIndex = pattern.lastIndex;
    }
    if (lastIndex < content.length) {
        blocks.push({ type: 'text', value: content.slice(lastIndex) });
    }
    if (blocks.length === 0) {
        blocks.push({ type: 'text', value: content });
    }
    return blocks;
};

export const extractFootnoteDefinitions = (text: string): FootnoteProcessResult => {
    const footnotes = new Map<string, FootnoteDefinition>();
    const definitionPattern = /^\[\^([^\]]+)\]:\s*(.+)$/gm;
    let processedText = text;
    const definitions: Array<{ fullMatch: string; id: string; content: string }> = [];
    let match: RegExpExecArray | null;
    while ((match = definitionPattern.exec(text)) !== null) {
        if (!match[1] || !match[2]) {
            continue;
        }
        definitions.push({
            fullMatch: match[0],
            id: match[1],
            content: match[2].trim()
        });
    }
    for (const definition of definitions) {
        footnotes.set(definition.id, {
            id: definition.id,
            content: definition.content
        });
        processedText = processedText.replace(definition.fullMatch, '');
    }
    processedText = processedText.replace(/\n{3,}/g, '\n\n');
    return { processedText, footnotes };
};

export const buildFootnotesSection = (footnotes: Map<string, FootnoteDefinition>, renderInlineText: (value: string, footnotesMap: Map<string, FootnoteDefinition>) => string, escapeHtml: (value: string) => string, translateBackRef: () => string): string => {
    if (footnotes.size === 0) {
        return '';
    }
    const usedFootnotes = Array.from(footnotes.values());
    if (usedFootnotes.length === 0) {
        return '';
    }
    let footnotesHtml = '<section class="footnotes-section"><hr class="footnotes-separator"><ol class="footnotes-list">';
    for (const footnote of usedFootnotes) {
        const escapedId = escapeHtml(footnote.id);
        const renderedContent = renderInlineText(footnote.content, footnotes);
        const backReferenceLabel = escapeHtml(translateBackRef());
        footnotesHtml += `<li id="fn-${escapedId}" class="footnote-item"><span class="footnote-content">${renderedContent}</span><a href="#fnref-${escapedId}" class="footnote-backref" aria-label="${backReferenceLabel}">↩</a></li>`;
    }
    footnotesHtml += '</ol></section>';
    return footnotesHtml;
};
