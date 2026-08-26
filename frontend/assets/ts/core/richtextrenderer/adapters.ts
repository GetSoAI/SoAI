/* SoAI - Shared rich text renderer adapters [frontend/assets/ts/core/richtextrenderer/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { FootnoteDefinition } from '@core/richtextrenderer/types.ts';
import { isHorizontalRuleLine, matchBlockquoteLine, matchHeadingLine, matchOrderedListLine, matchTaskListLine, matchUnorderedListLine } from '@core/richtextrenderer/richTextBlockSyntax.ts';
import { TABLE_END_TOKEN, TABLE_START_TOKEN } from '@core/richtextrenderer/tableRendering.ts';

const buildList = (type: 'ul' | 'ol', items: string[], start: number | null = null): string => {
    const listItems = items.map((item) => `<li>${item}</li>`).join('');
    const startAttribute = type === 'ol' && start !== null && start !== 1 ? ` start="${String(start)}"` : '';
    return `<${type}${startAttribute}>${listItems}</${type}>`;
};

const buildTaskList = (items: Array<{ content: string; checked?: boolean }>): string => {
    const listItems = items
        .map((item) => {
            const checkedAttribute = item.checked ? ' checked' : '';
            const checkedClass = item.checked ? ' task-list-item-checked' : '';
            return `<li class="task-list-item${checkedClass}"><input type="checkbox" class="task-list-checkbox" disabled${checkedAttribute}>${item.content}</li>`;
        })
        .join('');
    return `<ul class="task-list">${listItems}</ul>`;
};

export const processTextLines = (text: string, footnotes: Map<string, FootnoteDefinition> = new Map(), renderInlineText: (value: string, footnotesMap: Map<string, FootnoteDefinition>) => string): string => {
    const lines = text.split('\n');
    let html = '';
    let listType: 'ul' | 'ol' | 'task' | null = null;
    let listItems: Array<{ content: string; checked?: boolean }> = [];
    let orderedListStart: number | null = null;
    let blockquoteLines: string[] = [];
    let paragraphBuffer: string[] = [];

    const flushList = (): void => {
        if (!listType || listItems.length === 0) {
            listType = null;
            listItems = [];
            orderedListStart = null;
            return;
        }
        if (listType === 'task') {
            html += buildTaskList(listItems);
        } else {
            html += buildList(
                listType,
                listItems.map((item) => item.content),
                orderedListStart
            );
        }
        listType = null;
        listItems = [];
        orderedListStart = null;
    };

    const flushBlockquote = (): void => {
        if (blockquoteLines.length === 0) {
            return;
        }
        const content = blockquoteLines.map((line) => renderInlineText(line, footnotes)).join('<br>');
        html += `<blockquote>${content}</blockquote>`;
        blockquoteLines = [];
    };

    const flushParagraph = (): void => {
        if (paragraphBuffer.length === 0) {
            return;
        }
        const content = paragraphBuffer.join('\n');
        if (content.trim()) {
            html += `<p>${renderInlineText(content, footnotes)}</p>`;
        }
        paragraphBuffer = [];
    };

    const flushAll = (): void => {
        flushList();
        flushBlockquote();
        flushParagraph();
    };

    for (const rawLine of lines) {
        const line = rawLine.replace(/^\s+(?=(?:\d+\.\s+|[*\-+]\s+))/u, '');

        if (line.includes(TABLE_START_TOKEN)) {
            flushAll();
            const tableContent = line.replace(new RegExp(TABLE_START_TOKEN, 'g'), '').replace(new RegExp(TABLE_END_TOKEN, 'g'), '');
            html += tableContent;
            continue;
        }

        if (isHorizontalRuleLine(line)) {
            flushAll();
            html += '<hr>';
            continue;
        }

        const headerMatch = matchHeadingLine(line);
        if (headerMatch && headerMatch[1] && headerMatch[2]) {
            flushAll();
            const level = headerMatch[1].length;
            const content = renderInlineText(headerMatch[2], footnotes);
            html += `<h${level}>${content}</h${level}>`;
            continue;
        }

        const taskListMatch = matchTaskListLine(line);
        if (taskListMatch && taskListMatch[1] !== undefined && taskListMatch[2]) {
            flushBlockquote();
            flushParagraph();
            if (listType !== 'task') {
                flushList();
                listType = 'task';
            }
            const isChecked = taskListMatch[1].toLowerCase() === 'x';
            listItems.push({ content: renderInlineText(taskListMatch[2], footnotes), checked: isChecked });
            continue;
        }

        const ulMatch = matchUnorderedListLine(line);
        if (ulMatch && ulMatch[1]) {
            flushBlockquote();
            flushParagraph();
            if (listType !== 'ul') {
                flushList();
                listType = 'ul';
            }
            listItems.push({ content: renderInlineText(ulMatch[1], footnotes) });
            continue;
        }

        const olMatch = matchOrderedListLine(line);
        if (olMatch && olMatch[1] && olMatch[2]) {
            flushBlockquote();
            flushParagraph();
            if (listType !== 'ol') {
                flushList();
                listType = 'ol';
                orderedListStart = Number.parseInt(olMatch[1], 10);
            }
            listItems.push({ content: renderInlineText(olMatch[2], footnotes) });
            continue;
        }

        const blockquoteMatch = matchBlockquoteLine(line);
        if (blockquoteMatch && blockquoteMatch[1] !== undefined) {
            flushList();
            flushParagraph();
            const content = blockquoteMatch[1].trim();
            blockquoteLines.push(content);
            continue;
        }

        if (!line.trim()) {
            if (listType) {
                continue;
            }
            flushAll();
            continue;
        }

        flushList();
        flushBlockquote();
        paragraphBuffer.push(line);
    }

    flushAll();
    return html || '<p></p>';
};
