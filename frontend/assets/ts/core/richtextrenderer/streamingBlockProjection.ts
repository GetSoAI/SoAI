/* SoAI - Streaming rich-text immutable block projection [frontend/assets/ts/core/richtextrenderer/streamingBlockProjection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { computeHash } from '@core/primitives/hash.ts';
import { isCodeFenceLine, isCompleteTableRow, matchBlockquoteLine, matchHeadingLine, matchOrderedListLine, matchTaskListLine, matchUnorderedListLine } from '@core/richtextrenderer/richTextBlockSyntax.ts';
import { resolveLeadingClosedTableEnd, startsWithRenderableTable } from '@core/richtextrenderer/tableRendering.ts';

type StreamingRichBlockType = 'heading' | 'paragraph' | 'list' | 'blockquote' | 'table' | 'code';

type StreamingRichBlock = {
    type: StreamingRichBlockType;
    start: number;
    end: number;
    signature: string;
};

type StreamingRichBlockProjection = {
    source: string;
    immutableBlocks: StreamingRichBlock[];
    mutableStart: number;
    plainTextAppendSafe: boolean;
    reusedImmutableBlockCount: number;
};

type SourceRegion = {
    source: string;
    start: number;
    end: number;
};

const FOOTNOTE_PATTERN = /\[\^[^\]]+\]/;
const PREVIEW_TOKEN_START = '[[preview:';
const INLINE_RICH_TEXT_PATTERN = /`|[*_]|~~|<|\[|https?:\/\//iu;
const STREAMING_APPEND_BOUNDARY_PATTERN = /[\n`*_~<\[-]/u;
const AMBIGUOUS_BLOCK_PREFIX_PATTERN = /^\s*(?:#|[-+]|(?:\d+\.?\s*))$/u;

const resolveBlockType = (source: string): StreamingRichBlockType => {
    const lines = source.trimEnd().split('\n');
    const firstLine = lines[0] ?? '';
    if (isCodeFenceLine(firstLine)) {
        return 'code';
    }
    if (matchHeadingLine(firstLine)) {
        return 'heading';
    }
    if (matchTaskListLine(firstLine) || matchUnorderedListLine(firstLine) || matchOrderedListLine(firstLine)) {
        return 'list';
    }
    if (matchBlockquoteLine(firstLine)) {
        return 'blockquote';
    }
    if (lines.length >= 3 && startsWithRenderableTable(source)) {
        return 'table';
    }
    return 'paragraph';
};

const createBlock = (region: SourceRegion, sourceOffset: number): StreamingRichBlock => {
    const type = resolveBlockType(region.source);
    return {
        type,
        start: region.start + sourceOffset,
        end: region.end + sourceOffset,
        signature: `${type}:${String(region.source.length)}:${computeHash(region.source).toString(36)}`
    };
};

const collectClosedRegions = (source: string): SourceRegion[] => {
    const regions: SourceRegion[] = [];
    let regionStart = 0;
    let lineStart = 0;
    let openFence: string | null = null;
    while (lineStart < source.length) {
        const lineEnd = source.indexOf('\n', lineStart);
        const effectiveLineEnd = lineEnd < 0 ? source.length : lineEnd;
        const line = source.slice(lineStart, effectiveLineEnd);
        if (openFence === null && lineStart === regionStart && isCompleteTableRow(line)) {
            const tableEnd = resolveLeadingClosedTableEnd(source.slice(regionStart));
            if (tableEnd !== null) {
                const regionEnd = regionStart + tableEnd;
                regions.push({
                    source: source.slice(regionStart, regionEnd),
                    start: regionStart,
                    end: regionEnd
                });
                regionStart = regionEnd;
                lineStart = regionEnd;
                continue;
            }
        }
        if (isCodeFenceLine(line)) {
            openFence = openFence === null ? '```' : null;
        }
        if (openFence === null && line.trim() === '' && lineEnd >= 0) {
            let regionEnd = lineEnd + 1;
            while (regionEnd < source.length && source[regionEnd] === '\n') {
                regionEnd += 1;
            }
            if (source.slice(regionStart, regionEnd).trim()) {
                regions.push({
                    source: source.slice(regionStart, regionEnd),
                    start: regionStart,
                    end: regionEnd
                });
            }
            regionStart = regionEnd;
            lineStart = regionEnd;
            continue;
        }
        if (lineEnd < 0) {
            break;
        }
        lineStart = lineEnd + 1;
    }
    return regions;
};

const resolvePreviewDraftStart = (source: string): number => {
    let searchStart = 0;
    while (searchStart < source.length) {
        const tokenStart = source.indexOf(PREVIEW_TOKEN_START, searchStart);
        if (tokenStart < 0) {
            return -1;
        }
        const tokenEnd = source.indexOf(']]', tokenStart + PREVIEW_TOKEN_START.length);
        if (tokenEnd < 0) {
            return tokenStart;
        }
        searchStart = tokenEnd + 2;
    }
    return -1;
};

const projectStreamingSuffix = (source: string, sourceOffset: number): Omit<StreamingRichBlockProjection, 'source' | 'reusedImmutableBlockCount'> => {
    const footnoteStart = source.search(FOOTNOTE_PATTERN);
    const previewStart = resolvePreviewDraftStart(source);
    const dependencyStarts = [footnoteStart, previewStart].filter((index) => index >= 0);
    const dependencyStart = dependencyStarts.length > 0 ? Math.min(...dependencyStarts) : source.length;
    const regions = collectClosedRegions(source).filter((region) => region.end <= dependencyStart);
    const localMutableStart = regions.at(-1)?.end ?? 0;
    const mutableSource = source.slice(localMutableStart);
    const mutableType = mutableSource.trim() ? resolveBlockType(mutableSource) : null;
    return {
        immutableBlocks: regions.map((region) => createBlock(region, sourceOffset)),
        mutableStart: localMutableStart + sourceOffset,
        plainTextAppendSafe: mutableType === 'paragraph' && !INLINE_RICH_TEXT_PATTERN.test(mutableSource) && !AMBIGUOUS_BLOCK_PREFIX_PATTERN.test(mutableSource)
    };
};

const projectStreamingRichTextBlocks = (source: string, previousProjection: StreamingRichBlockProjection | null = null): StreamingRichBlockProjection => {
    if (previousProjection !== null && source.startsWith(previousProjection.source)) {
        const suffix = projectStreamingSuffix(source.slice(previousProjection.mutableStart), previousProjection.mutableStart);
        return {
            source,
            immutableBlocks: [...previousProjection.immutableBlocks, ...suffix.immutableBlocks],
            mutableStart: suffix.mutableStart,
            plainTextAppendSafe: suffix.plainTextAppendSafe,
            reusedImmutableBlockCount: previousProjection.immutableBlocks.length
        };
    }
    const projection = projectStreamingSuffix(source, 0);
    return {
        source,
        ...projection,
        reusedImmutableBlockCount: 0
    };
};

const resolveStreamingMutableSource = (projection: StreamingRichBlockProjection): string => projection.source.slice(projection.mutableStart);

const streamingMarkdownAppendRequiresCanonicalRender = (existingPlainTextSuffix: string, appendText: string): boolean => {
    if (STREAMING_APPEND_BOUNDARY_PATTERN.test(appendText)) {
        return true;
    }
    return /https?:\/\//iu.test(`${existingPlainTextSuffix.slice(-8)}${appendText}`);
};

export { projectStreamingRichTextBlocks, resolveStreamingMutableSource, streamingMarkdownAppendRequiresCanonicalRender };
export type { StreamingRichBlock, StreamingRichBlockProjection, StreamingRichBlockType };
