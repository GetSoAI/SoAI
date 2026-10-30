/* SoAI - Policy-driven searchable text blocks and DOM range mapping [frontend/assets/ts/core/search/domTextIndex.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isElementNodeLike } from '@core/dom/domEnvironment.ts';
import { isLiteralSearchOffsetBoundary } from '@core/search/literalOccurrences.ts';
import type { SearchWorkBudget } from '@core/search/searchWorkBudget.ts';

type SearchTextTraversalPolicy = (element: Element) => 'exclude' | 'boundary' | 'inline';

interface SearchTextSpan {
    node: Text;
    start: number;
    end: number;
}

interface SearchTextBlock {
    text: string;
    spans: readonly SearchTextSpan[];
}

const isTextNode = (node: Node): node is Text => node.nodeType === 3;

const visitSearchTextBlocks = async (root: Node, policy: SearchTextTraversalPolicy, budget: SearchWorkBudget, visitBlock: (block: SearchTextBlock) => Promise<boolean>, captureTextNodes = true): Promise<boolean> => {
    await budget.checkpoint();
    let parts: string[] = [];
    let spans: SearchTextSpan[] = [];
    let length = 0;
    let visitedNodes = 0;
    const flush = async (): Promise<boolean> => {
        if (length === 0) return true;
        const block = { text: parts.join(''), spans };
        parts = [];
        spans = [];
        length = 0;
        const shouldContinue = await visitBlock(block);
        await budget.checkpoint();
        return shouldContinue;
    };
    const boundaries = new Set<Node>();
    let current: Node | null = root;
    while (current !== null) {
        visitedNodes += 1;
        if (visitedNodes % 128 === 0) await budget.checkpoint();
        const decision = isElementNodeLike(current) ? policy(current) : 'inline';
        if (decision !== 'inline' && !(await flush())) return false;
        if (decision === 'boundary') boundaries.add(current);
        if (decision !== 'exclude') {
            if (isTextNode(current) && current.data.length > 0) {
                parts.push(current.data);
                if (captureTextNodes) spans.push({ node: current, start: length, end: length + current.data.length });
                length += current.data.length;
            }
            if (current.firstChild !== null) {
                current = current.firstChild;
                continue;
            }
        }
        while (current !== null) {
            if (boundaries.delete(current) && !(await flush())) return false;
            if (current === root) return await flush();
            if (current.nextSibling !== null) {
                current = current.nextSibling;
                break;
            }
            current = current.parentNode;
        }
    }
    return await flush();
};

const createSearchTextRange = (block: SearchTextBlock, offset: number, length: number): Range | null => {
    const end = offset + length;
    if (!Number.isSafeInteger(offset) || !Number.isSafeInteger(length) || offset < 0 || length < 1 || end > block.text.length) return null;
    if (!isLiteralSearchOffsetBoundary(block.text, offset) || !isLiteralSearchOffsetBoundary(block.text, end)) return null;
    const first = block.spans.find((span) => span.start <= offset && span.end > offset);
    const last = block.spans.find((span) => span.start < end && span.end >= end);
    if (!first || !last || first.node.ownerDocument !== last.node.ownerDocument) return null;
    for (const span of block.spans) {
        if (span.end <= offset) continue;
        if (span.start >= end) break;
        if (span.node.data !== block.text.slice(span.start, span.end)) return null;
    }
    const range = first.node.ownerDocument.createRange();
    range.setStart(first.node, offset - first.start);
    range.setEnd(last.node, end - last.start);
    return range.toString() === block.text.slice(offset, end) ? range : null;
};

export { createSearchTextRange, visitSearchTextBlocks };
export type { SearchTextBlock, SearchTextSpan, SearchTextTraversalPolicy };
