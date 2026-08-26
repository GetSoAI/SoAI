/* SoAI - Shared rich text renderer table rendering [frontend/assets/ts/core/richtextrenderer/tableRendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RichTextTableMode } from '@core/richtextrenderer/types.ts';
import { computeHash } from '@core/primitives/hash.ts';
import { isCompleteTableRow, isStreamingTableRow, isTableRowStartLine, isTableSeparatorRow } from '@core/richtextrenderer/richTextBlockSyntax.ts';

const TABLE_START_TOKEN = '\x00TABLE_START\x00';
const TABLE_END_TOKEN = '\x00TABLE_END\x00';

type TableAlignment = 'left' | 'center' | 'right' | null;
type RenderableTableRows = { rows: string[]; nextIndex: number };
type TableRenderingOptions = {
    tableMode: RichTextTableMode;
    tableSortAction: string | null;
    escapeAttribute: (value: string) => string;
};

const parseTableAlignments = (separatorRow: string): TableAlignment[] => {
    const cells = parseTableRow(separatorRow);
    return cells.map((cell) => {
        const trimmed = cell.trim();
        const startsWithColon = trimmed.startsWith(':');
        const endsWithColon = trimmed.endsWith(':');
        if (startsWithColon && endsWithColon) {
            return 'center';
        }
        if (endsWithColon) {
            return 'right';
        }
        if (startsWithColon) {
            return 'left';
        }
        return null;
    });
};

const parseTableRow = (row: string): string[] => {
    const trimmed = row.trim();
    const withoutPipes = trimmed.startsWith('|') ? trimmed.slice(1) : trimmed;
    const cleaned = withoutPipes.endsWith('|') ? withoutPipes.slice(0, -1) : withoutPipes;
    return cleaned.split('|').map((cell) => cell.trim());
};

const resolveTableCellAlignmentClass = (alignment: TableAlignment): string | null => {
    if (alignment === 'left') {
        return 'u-text-left';
    }
    if (alignment === 'center') {
        return 'u-text-center';
    }
    if (alignment === 'right') {
        return 'u-text-right';
    }
    return null;
};

const formatTableCellClass = (alignment: TableAlignment, additionalClass: string | null = null): string => {
    const classNames = [resolveTableCellAlignmentClass(alignment), additionalClass].filter((className): className is string => className !== null);
    return classNames.length > 0 ? ` class="${classNames.join(' ')}"` : '';
};

const wrapTableMarkup = (tableHtml: string): string => {
    return `<div class="markdown-table-scroll">${tableHtml}</div>`;
};

const parseGfmTable = (headerRow: string, separatorRow: string, bodyRows: readonly string[], renderInlineText: (value: string) => string, options: TableRenderingOptions): string | null => {
    const headerCells = parseTableRow(headerRow);
    const alignments = parseTableAlignments(separatorRow);
    if (headerCells.length === 0 || alignments.length === 0 || headerCells.length !== alignments.length) {
        return null;
    }
    const bodyRowsCells = bodyRows.map((row) => parseTableRow(row));
    const sortAction = options.tableSortAction;
    const sortingEnabled = sortAction !== null;
    let tableAttributes = ' class="markdown-table"';
    let escapedSortAction: string | null = null;
    if (sortAction !== null) {
        const tableSource = `${headerRow}\n${separatorRow}\n${bodyRows.join('\n')}`;
        const tableKey = computeHash(tableSource).toString(36);
        tableAttributes = ` class="markdown-table markdown-table-sortable" data-markdown-table-key="${tableKey}"`;
        escapedSortAction = options.escapeAttribute(sortAction);
    }
    let tableHtml = `<table${tableAttributes}><thead><tr>`;
    for (let columnIndex = 0; columnIndex < headerCells.length; columnIndex += 1) {
        const alignment = alignments[columnIndex] ?? null;
        const cellContent = renderInlineText(headerCells[columnIndex] ?? '');
        if (escapedSortAction !== null) {
            const classAttribute = formatTableCellClass(alignment, 'markdown-table-sortable-header');
            const escapedLabel = options.escapeAttribute(headerCells[columnIndex] ?? '');
            tableHtml += `<th${classAttribute} scope="col" tabindex="0" aria-sort="none" aria-label="${escapedLabel}" data-tooltip="${escapedLabel}" data-action="${escapedSortAction}" data-sort="${String(columnIndex)}">${cellContent}<span class="sort-indicator" aria-hidden="true"></span></th>`;
        } else {
            tableHtml += `<th${formatTableCellClass(alignment)}>${cellContent}</th>`;
        }
    }
    tableHtml += '</tr></thead><tbody>';
    for (let rowIndex = 0; rowIndex < bodyRowsCells.length; rowIndex += 1) {
        const rowCells = bodyRowsCells[rowIndex] ?? [];
        tableHtml += sortingEnabled ? `<tr data-markdown-table-source-index="${String(rowIndex)}">` : '<tr>';
        for (let columnIndex = 0; columnIndex < headerCells.length; columnIndex += 1) {
            const alignment = alignments[columnIndex] ?? null;
            const cellContent = renderInlineText(rowCells[columnIndex] ?? '');
            tableHtml += `<td${formatTableCellClass(alignment)}>${cellContent}</td>`;
        }
        tableHtml += '</tr>';
    }
    tableHtml += '</tbody></table>';
    return wrapTableMarkup(tableHtml);
};

const hasRenderableTableShape = (headerRow: string, separatorRow: string): boolean => {
    const headerCells = parseTableRow(headerRow);
    const alignments = parseTableAlignments(separatorRow);
    return headerCells.length > 0 && alignments.length > 0 && headerCells.length === alignments.length;
};

const collectTableBodyRows = (lines: readonly string[], startIndex: number, tableMode: RichTextTableMode): { rows: string[]; nextIndex: number } => {
    const rows: string[] = [];
    let lineIndex = startIndex;
    while (lineIndex < lines.length) {
        const line = lines[lineIndex] ?? '';
        if (isCompleteTableRow(line)) {
            rows.push(line);
            lineIndex += 1;
            continue;
        }
        if (tableMode === 'streaming' && lineIndex === lines.length - 1 && isStreamingTableRow(line)) {
            rows.push(line);
            lineIndex += 1;
        }
        break;
    }
    return { rows, nextIndex: lineIndex };
};

const resolveRenderableTableRows = (lines: readonly string[], lineIndex: number, tableMode: RichTextTableMode): RenderableTableRows | null => {
    const headerRow = lines[lineIndex] ?? '';
    const separatorRow = lines[lineIndex + 1] ?? '';
    if (!isCompleteTableRow(headerRow) || !isCompleteTableRow(separatorRow) || !isTableSeparatorRow(separatorRow) || !hasRenderableTableShape(headerRow, separatorRow)) {
        return null;
    }
    const body = collectTableBodyRows(lines, lineIndex + 2, tableMode);
    return body.rows.length > 0 ? body : null;
};

const processTablesInText = (text: string, inlineRenderer: (value: string) => string, options: TableRenderingOptions): string => {
    const lines = text.split('\n');
    const processedLines: string[] = [];
    let lineIndex = 0;
    while (lineIndex < lines.length) {
        const headerRow = lines[lineIndex] ?? '';
        const separatorRow = lines[lineIndex + 1] ?? '';
        const tableRows = resolveRenderableTableRows(lines, lineIndex, options.tableMode);
        if (tableRows !== null) {
            const parsedTable = parseGfmTable(headerRow, separatorRow, tableRows.rows, inlineRenderer, options);
            if (parsedTable) {
                processedLines.push(`${TABLE_START_TOKEN}${parsedTable}${TABLE_END_TOKEN}`);
                lineIndex = tableRows.nextIndex;
                continue;
            }
        }
        processedLines.push(headerRow);
        lineIndex += 1;
    }
    return processedLines.join('\n');
};

const startsWithRenderableTable = (text: string, tableMode: RichTextTableMode = 'strict'): boolean => {
    return resolveRenderableTableRows(text.split('\n'), 0, tableMode) !== null;
};

const resolveLeadingClosedTableEnd = (text: string): number | null => {
    const lines = text.split('\n');
    const tableRows = resolveRenderableTableRows(lines, 0, 'strict');
    if (tableRows === null || tableRows.nextIndex >= lines.length) {
        return null;
    }
    const followingLine = lines[tableRows.nextIndex] ?? '';
    if (!followingLine.trim() || isTableRowStartLine(followingLine)) {
        return null;
    }
    const offsets = buildLineStartOffsets(lines);
    return offsets[tableRows.nextIndex] ?? null;
};

const buildLineStartOffsets = (lines: readonly string[]): number[] => {
    const offsets: number[] = [];
    let offset = 0;
    for (const line of lines) {
        offsets.push(offset);
        offset += line.length + 1;
    }
    return offsets;
};

export { processTablesInText, resolveLeadingClosedTableEnd, startsWithRenderableTable, TABLE_END_TOKEN, TABLE_START_TOKEN };
