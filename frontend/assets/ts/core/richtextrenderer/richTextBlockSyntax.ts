/* SoAI - Canonical rich-text block syntax recognition [frontend/assets/ts/core/richtextrenderer/richTextBlockSyntax.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const createFencedCodeBlockPattern = (): RegExp => /```([^\n`]*)\s*\n([\s\S]*?)```/g;

const isCodeFenceLine = (line: string): boolean => line.trimStart().startsWith('```');

const matchHeadingLine = (line: string): RegExpExecArray | null => /^(#{1,6})\s+(.+)$/u.exec(line);

const matchTaskListLine = (line: string): RegExpExecArray | null => /^\s*[*\-+]\s+\[([ xX])\]\s+(.+)$/u.exec(line);

const matchUnorderedListLine = (line: string): RegExpExecArray | null => /^\s*[*\-+]\s+(.+)$/u.exec(line);

const matchOrderedListLine = (line: string): RegExpExecArray | null => /^\s*(\d+)\.\s+(.+)$/u.exec(line);

const matchBlockquoteLine = (line: string): RegExpExecArray | null => /^>\s*(.*)$/u.exec(line);

const isHorizontalRuleLine = (line: string): boolean => /^(?:---+|\*\*\*+|___+)\s*$/u.test(line.trim());

const isCompleteTableRow = (row: string): boolean => {
    const trimmed = row.trim();
    return trimmed.startsWith('|') && trimmed.endsWith('|') && trimmed.length > 1;
};

const isStreamingTableRow = (row: string): boolean => {
    const trimmed = row.trim();
    return trimmed.startsWith('|') && trimmed.length > 1;
};

const isTableRowStartLine = (row: string): boolean => row.trim().startsWith('|');

const isTableSeparatorRow = (row: string): boolean => /^\|[-:\s|]+\|$/u.test(row.trim());

export { createFencedCodeBlockPattern, isCodeFenceLine, isCompleteTableRow, isHorizontalRuleLine, isStreamingTableRow, isTableRowStartLine, isTableSeparatorRow, matchBlockquoteLine, matchHeadingLine, matchOrderedListLine, matchTaskListLine, matchUnorderedListLine };
