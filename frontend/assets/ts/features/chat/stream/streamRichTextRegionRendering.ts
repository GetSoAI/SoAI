/* SoAI - Streaming rich text region rendering for active chat message text [frontend/assets/ts/features/chat/stream/streamRichTextRegionRendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createHtmlFragment } from '@core/dom/html.ts';
import { projectStreamingRichTextBlocks, resolveStreamingMutableRenderSource, resolveStreamingMutableSource, type StreamingRichBlock, type StreamingRichBlockProjection } from '@core/richtextrenderer/streamingBlockProjection.ts';
import type { RenderedStreamingBlockRecord, StreamingElementCache } from '@features/chat/stream/streamDomCache.ts';
import type { StreamMessageManager } from '@features/chat/stream/streamMessageRenderingContracts.ts';
import { patchRichTextContent } from '@features/chat/stream/streamRichTextPatching.ts';
import { patchStreamingPlainTextContinuation, type StreamingPlainTextTailPatchResult } from '@features/chat/stream/streamRichTextTailContinuation.ts';

type StreamingRegionRenderArguments = {
    cached: StreamingElementCache;
    messageManager: StreamMessageManager;
    source: string;
};

type StreamingRegionRenderResult = {
    updated: boolean;
    postRenderTargets: HTMLElement[];
};

const isMermaidCodeFenceLanguageHint = (languageHint: string): boolean => {
    const normalized = languageHint.trim().toLowerCase();
    return normalized === 'mmd' || normalized === 'mermaid' || normalized.startsWith('mermaid');
};

const resolveTrailingOpenCodeFence = (source: string): { prefix: string; languageHint: string; code: string } | null => {
    let lineStartIndex = 0;
    let openFence: { prefix: string; languageHint: string; code: string } | null = null;
    while (lineStartIndex <= source.length) {
        const lineEndIndex = source.indexOf('\n', lineStartIndex);
        const effectiveLineEndIndex = lineEndIndex >= 0 ? lineEndIndex : source.length;
        const line = source.slice(lineStartIndex, effectiveLineEndIndex);
        const trimmedStart = line.trimStart();
        if (trimmedStart.startsWith('```')) {
            if (openFence === null && lineEndIndex < 0) {
                break;
            }
            const markerStartIndex = lineStartIndex + line.length - trimmedStart.length;
            if (openFence === null) {
                openFence = {
                    prefix: source.slice(0, markerStartIndex),
                    languageHint: trimmedStart.slice(3),
                    code: source.slice(lineEndIndex >= 0 ? lineEndIndex + 1 : source.length)
                };
            } else {
                openFence = null;
            }
        }
        if (lineEndIndex < 0) {
            break;
        }
        lineStartIndex = lineEndIndex + 1;
    }
    return openFence;
};

const renderMutableMarkdownSource = (source: string, messageManager: StreamMessageManager): string => {
    const openFence = resolveTrailingOpenCodeFence(source);
    if (openFence === null) {
        const renderSource = resolveStreamingMutableRenderSource(source);
        return renderSource.trim() ? messageManager.renderStreamingMarkdownContent(renderSource) : '';
    }
    const prefixHtml = openFence.prefix.trim() ? messageManager.renderStreamingMarkdownContent(openFence.prefix) : '';
    const normalizedCode = openFence.code.endsWith('\n') ? openFence.code : `${openFence.code}\n`;
    const languageHint = isMermaidCodeFenceLanguageHint(openFence.languageHint) ? '' : openFence.languageHint.trim();
    return `${prefixHtml}${messageManager.renderMarkdownContent(`\`\`\`${languageHint}\n${normalizedCode}\`\`\``)}`;
};

const parseRenderedBlock = (container: HTMLElement, block: StreamingRichBlock, markup: string): RenderedStreamingBlockRecord => {
    const fragment = createHtmlFragment({
        documentRef: container.ownerDocument,
        html: markup,
        context: container
    });
    const nodes = Array.from(fragment.children).filter((element): element is HTMLElement => element instanceof HTMLElement);
    if (nodes.length === 0 || Array.from(fragment.childNodes).some((node) => node.nodeType === Node.TEXT_NODE && node.textContent?.trim())) {
        throw new Error('Streaming rich-text immutable block did not produce canonical element children');
    }
    container.appendChild(fragment);
    return {
        ...block,
        nodes
    };
};

const incrementalCacheIsValid = (cached: StreamingElementCache, settled: HTMLElement, tail: HTMLElement): boolean => {
    const streamText = cached.streamText;
    if (!(streamText instanceof HTMLElement) || settled.parentElement !== streamText || tail.parentElement !== streamText || settled === tail || settled.childElementCount !== cached.renderedRichNodeCount) {
        return false;
    }
    const firstNode = cached.renderedRichBlocks[0]?.nodes[0] ?? null;
    const lastRecord = cached.renderedRichBlocks.at(-1);
    const lastNode = lastRecord?.nodes.at(-1) ?? null;
    return (firstNode === null || firstNode.parentElement === settled) && (lastNode === null || lastNode.parentElement === settled);
};

const cacheIsValid = (cached: StreamingElementCache, settled: HTMLElement): boolean => {
    const streamText = cached.streamText;
    const tail = cached.streamTextTail;
    if (!(streamText instanceof HTMLElement) || !(tail instanceof HTMLElement) || settled.parentElement !== streamText || tail.parentElement !== streamText || settled === tail) {
        return false;
    }
    const cachedProjection = cached.richTextProjection;
    if (cachedProjection === null && cached.renderedRichBlocks.length > 0) {
        return false;
    }
    const expectedNodes: HTMLElement[] = [];
    for (let index = 0; index < cached.renderedRichBlocks.length; index += 1) {
        const record = cached.renderedRichBlocks[index];
        const projected = cachedProjection?.immutableBlocks[index];
        if (!record || !projected || record.start !== projected.start || record.end !== projected.end || record.signature !== projected.signature) {
            return false;
        }
        if (record.nodes.length === 0 || record.nodes.some((node) => node.parentElement !== settled)) {
            return false;
        }
        expectedNodes.push(...record.nodes);
    }
    const settledChildren = Array.from(settled.children);
    return settledChildren.length === cached.renderedRichNodeCount && settledChildren.length === expectedNodes.length && settledChildren.every((node, index) => node === expectedNodes[index]);
};

const removeBlocksFrom = (cached: StreamingElementCache, index: number): void => {
    for (const record of cached.renderedRichBlocks.slice(index)) {
        cached.renderedRichNodeCount -= record.nodes.length;
        for (const node of record.nodes) {
            node.remove();
        }
    }
    cached.renderedRichBlocks.splice(index);
};

const retainMatchingPrefix = (cached: StreamingElementCache, blocks: readonly StreamingRichBlock[]): number => {
    let matchingCount = 0;
    while (matchingCount < cached.renderedRichBlocks.length && matchingCount < blocks.length) {
        const current = cached.renderedRichBlocks[matchingCount];
        const next = blocks[matchingCount];
        if (!current || !next || current.signature !== next.signature || current.start !== next.start || current.end !== next.end) {
            break;
        }
        matchingCount += 1;
    }
    removeBlocksFrom(cached, matchingCount);
    return matchingCount;
};

const canPromoteMutableTail = (cached: StreamingElementCache, projection: StreamingRichBlockProjection, block: StreamingRichBlock, tail: HTMLElement): boolean => {
    const previousProjection = cached.richTextProjection;
    if (previousProjection === null || tail.children.length === 0) {
        return false;
    }
    const previousMutableSource = resolveStreamingMutableSource(previousProjection);
    const blockSource = projection.source.slice(block.start, block.end);
    if (!previousMutableSource || resolveStreamingMutableRenderSource(previousMutableSource) !== previousMutableSource || !blockSource.startsWith(previousMutableSource)) {
        return false;
    }
    return blockSource.slice(previousMutableSource.length).trim() === '';
};

const promoteMutableTail = (settled: HTMLElement, tail: HTMLElement, block: StreamingRichBlock): RenderedStreamingBlockRecord => {
    const nodes = Array.from(tail.children).filter((element): element is HTMLElement => element instanceof HTMLElement);
    for (const node of nodes) {
        settled.appendChild(node);
    }
    return {
        ...block,
        nodes
    };
};

const renderImmutableBlocks = (inputArguments: StreamingRegionRenderArguments, projection: StreamingRichBlockProjection, settled: HTMLElement, tail: HTMLElement, blocks: readonly StreamingRichBlock[], startIndex: number): { changedNodes: HTMLElement[]; promotedTail: boolean } => {
    const changedNodes: HTMLElement[] = [];
    let promotedTail = false;
    for (let index = startIndex; index < blocks.length; index += 1) {
        const block = blocks[index];
        if (!block) {
            continue;
        }
        const blockSource = projection.source.slice(block.start, block.end);
        if (index === startIndex && canPromoteMutableTail(inputArguments.cached, projection, block, tail)) {
            if (block.type === 'table') {
                const sortableMarkup = inputArguments.messageManager.renderMarkdownContent(blockSource, { sortableTables: true });
                patchRichTextContent(tail, sortableMarkup);
            }
            const promoted = promoteMutableTail(settled, tail, block);
            inputArguments.cached.renderedRichBlocks.push(promoted);
            inputArguments.cached.renderedRichNodeCount += promoted.nodes.length;
            promotedTail = true;
            continue;
        }
        const markup = block.type === 'table' ? inputArguments.messageManager.renderMarkdownContent(blockSource, { sortableTables: true }) : inputArguments.messageManager.renderStreamingMarkdownContent(blockSource);
        const rendered = parseRenderedBlock(settled, block, markup);
        inputArguments.cached.renderedRichBlocks.push(rendered);
        inputArguments.cached.renderedRichNodeCount += rendered.nodes.length;
        changedNodes.push(...rendered.nodes);
    }
    return { changedNodes, promotedTail };
};

const rebuildCanonicalRegion = (inputArguments: StreamingRegionRenderArguments, settled: HTMLElement, tail: HTMLElement): boolean => {
    const changed = settled.hasChildNodes() || tail.hasChildNodes();
    settled.textContent = '';
    tail.textContent = '';
    inputArguments.cached.renderedRichBlocks = [];
    inputArguments.cached.renderedRichNodeCount = 0;
    return changed;
};

const clearStreamingRichTextRegion = (cached: StreamingElementCache): void => {
    cached.streamTextSettled?.replaceChildren();
    cached.streamTextTail?.replaceChildren();
    cached.renderedRichBlocks = [];
    cached.renderedRichNodeCount = 0;
    cached.richTextRenderEpoch = null;
    cached.richTextProjection = null;
};

const patchStreamingPlainTextTail = (cached: StreamingElementCache, appendText: string): StreamingPlainTextTailPatchResult => {
    const tail = cached.streamTextTail;
    if (!(tail instanceof HTMLElement)) {
        throw new Error('Streaming rich text tail is unavailable');
    }
    return patchStreamingPlainTextContinuation({ tail, appendText });
};

const renderStreamingRichTextRegion = (inputArguments: StreamingRegionRenderArguments): StreamingRegionRenderResult => {
    const settled = inputArguments.cached.streamTextSettled;
    const tail = inputArguments.cached.streamTextTail;
    if (!(settled instanceof HTMLElement) || !(tail instanceof HTMLElement)) {
        throw new Error('Streaming rich text containers are unavailable');
    }
    const source = inputArguments.source;
    const previousProjection = inputArguments.cached.richTextProjection;
    const previousMutableSource = previousProjection === null ? null : resolveStreamingMutableSource(previousProjection);
    const projection = projectStreamingRichTextBlocks(source, inputArguments.cached.richTextProjection);
    const renderEpoch = inputArguments.messageManager.getWorkerRenderEpoch();
    const incrementalProjectionMatchesCache = inputArguments.cached.richTextRenderEpoch === renderEpoch && projection.reusedImmutableBlockCount === inputArguments.cached.renderedRichBlocks.length && incrementalCacheIsValid(inputArguments.cached, settled, tail);
    const rebuilt = !incrementalProjectionMatchesCache && (inputArguments.cached.richTextRenderEpoch !== renderEpoch || !cacheIsValid(inputArguments.cached, settled));
    const rebuiltContentChanged = rebuilt ? rebuildCanonicalRegion(inputArguments, settled, tail) : false;
    const matchingCount = incrementalProjectionMatchesCache ? inputArguments.cached.renderedRichBlocks.length : retainMatchingPrefix(inputArguments.cached, projection.immutableBlocks);
    const immutableRender = renderImmutableBlocks(inputArguments, projection, settled, tail, projection.immutableBlocks, matchingCount);
    const changedNodes = immutableRender.changedNodes;
    const mutableSource = resolveStreamingMutableSource(projection);
    const tailChanged = rebuilt || immutableRender.promotedTail ? tail.textContent !== '' || mutableSource !== '' : previousMutableSource !== mutableSource;
    if (tailChanged) {
        const tailMarkup = renderMutableMarkdownSource(mutableSource, inputArguments.messageManager);
        patchRichTextContent(tail, tailMarkup);
        changedNodes.push(...Array.from(tail.children).filter((element): element is HTMLElement => element instanceof HTMLElement));
    }
    inputArguments.cached.richTextRenderEpoch = renderEpoch;
    inputArguments.cached.richTextProjection = projection;
    return {
        updated: rebuiltContentChanged || changedNodes.length > 0 || tailChanged,
        postRenderTargets: Array.from(new Set(changedNodes))
    };
};

export { clearStreamingRichTextRegion, patchStreamingPlainTextTail, renderStreamingRichTextRegion };
export type { StreamingPlainTextTailPatchResult };
