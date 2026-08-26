/* SoAI - Grep files tool result presentation model [frontend/assets/ts/features/chat/toolactivity/grepFilesPresentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonArray, isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isNonEmptyString, isNonNegativeInteger, isPositiveInteger, isString } from '@core/typeGuards.ts';

type GrepLine = {
    lineNumber: number;
    text: string;
    isContext: boolean;
};

type GrepFile = {
    path: string;
    matchCount: number | null;
    lines: GrepLine[];
};

const parseGrepLine = (value: JsonValue | undefined): GrepLine | null => {
    if (!isJsonObject(value)) {
        return null;
    }
    const lineNumber = value['line_number'];
    const text = value['text'];
    const isContext = value['is_context'];
    if (!isPositiveInteger(lineNumber) || !isString(text) || typeof isContext !== 'boolean') {
        return null;
    }
    return { lineNumber, text, isContext };
};

const parseGrepFile = (value: JsonValue | undefined): GrepFile | null => {
    if (!isJsonObject(value)) {
        return null;
    }
    const path = value['path'];
    const lines = value['lines'];
    if (!isNonEmptyString(path) || !isJsonArray(lines)) {
        return null;
    }
    const parsedLines: GrepLine[] = [];
    for (const line of lines) {
        const parsedLine = parseGrepLine(line);
        if (parsedLine === null) {
            return null;
        }
        parsedLines.push(parsedLine);
    }
    return {
        path,
        matchCount: isNonNegativeInteger(value['match_count']) ? value['match_count'] : null,
        lines: parsedLines
    };
};

const parseGrepFiles = (value: JsonValue | undefined): GrepFile[] | null => {
    if (!isJsonArray(value)) {
        return null;
    }
    const files: GrepFile[] = [];
    for (const entry of value) {
        const parsedFile = parseGrepFile(entry);
        if (parsedFile === null) {
            return null;
        }
        files.push(parsedFile);
    }
    return files;
};

const formatGrepFileHeader = (file: GrepFile): string => {
    if (file.matchCount === null) {
        return file.path;
    }
    return `${file.path} (${String(file.matchCount)})`;
};

const formatGrepLine = (line: GrepLine): string => {
    const marker = line.isContext ? ' ' : '>';
    return `${marker} ${String(line.lineNumber).padStart(6, ' ')} | ${line.text}`;
};

const formatGrepMatches = (files: GrepFile[]): string => {
    const blocks: string[] = [];
    for (const file of files) {
        if (file.lines.length === 0) {
            blocks.push(formatGrepFileHeader(file));
            continue;
        }
        const lines = file.lines.map(formatGrepLine);
        blocks.push([formatGrepFileHeader(file), ...lines].join('\n'));
    }
    return blocks.join('\n\n');
};

const buildGrepFilesDisplayRecord = (resultRecord: JsonObject): JsonObject | null => {
    const files = parseGrepFiles(resultRecord['files']);
    if (files === null) {
        return null;
    }
    const displayRecord: JsonObject = {};
    for (const key of ['pattern', 'include', 'path', 'output_mode', 'total_matches', 'truncated', 'truncated_reason']) {
        const value = resultRecord[key];
        if (value !== undefined) {
            displayRecord[key] = value;
        }
    }
    const matches = formatGrepMatches(files);
    if (matches) {
        displayRecord['matches'] = matches;
    }
    return displayRecord;
};

export { buildGrepFilesDisplayRecord };
