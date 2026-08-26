/* SoAI - Canonical preview token scanning and in-place pending-card replacement [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaTokenParsing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import { createInlineMediaPendingCard } from '@features/chat/message/enhancers/inlineMultimediaPendingCard.ts';
import { isElementInOwnDocument, isHTMLElementInOwnDocument, isTextInOwnDocument, shouldSkipInlineMediaSurface } from '@features/chat/message/enhancers/inlineMultimediaDomSafety.ts';
import { PREVIEW_REFERENCE_PATTERN, parsePreviewReferenceTokenMatch, type PreviewReferenceToken, type PreviewReferenceType } from '@features/chat/message/enhancers/inlineMultimediaPreviewContract.ts';
import { resolveInlineMultimediaPreviewTokenRoute } from '@features/chat/message/enhancers/inlineMultimediaPreviewTokenResolution.ts';

type InlineMediaTokenType = PreviewReferenceType;
type InlineMediaToken = PreviewReferenceToken;
type InlineMediaTokenRenderer = (doc: Document, token: InlineMediaToken) => Node;
type InlineMediaOptionalTokenRenderer = (doc: Document, token: InlineMediaToken) => Node | null;

interface InlineMediaTokenNodeMatch {
    token: InlineMediaToken;
    startIndex: number;
    endIndex: number;
}

interface InlineMediaTokenNodePlan {
    node: Text;
    text: string;
    matches: InlineMediaTokenNodeMatch[];
}

interface InlineMediaTokenNodeReplacement {
    match: InlineMediaTokenNodeMatch;
    replacement: Node | null;
}

const DISALLOWED_TAG_NAMES = new Set<string>(['A', 'BUTTON', 'TEXTAREA', 'INPUT', 'SELECT', 'PRE', 'CODE']);

const isTokenTextCandidate = (text: string): boolean => text.includes('[[preview:') && text.includes(']]');

const isStreamingTailElement = (element: Element): boolean => {
    return isHTMLElementInOwnDocument(element) && element.dataset['streamTextTail'] === 'true';
};

const isDisallowedTraversalElement = (element: Element): boolean => {
    if (!isHTMLElementInOwnDocument(element)) {
        return false;
    }
    if (DISALLOWED_TAG_NAMES.has(element.tagName)) {
        return true;
    }
    if (shouldSkipInlineMediaSurface(element)) {
        return true;
    }
    if (element.classList.contains('inline-activity-type-tool')) {
        return true;
    }
    return element.hasAttribute('data-action');
};

const shouldSkipTraversalForElement = (element: Element, options: { includeStreamingTail: boolean }): boolean => {
    if (!options.includeStreamingTail && isStreamingTailElement(element)) {
        return true;
    }
    if (isDisallowedTraversalElement(element)) {
        return true;
    }
    return false;
};

const isTextNodeEligible = (node: Text): boolean => {
    const parent = node.parentElement;
    if (!parent) {
        return false;
    }
    const text = node.nodeValue ?? '';
    return Boolean(text.trim()) && isTokenTextCandidate(text);
};

const collectInlineMediaTokenNodePlans = (container: HTMLElement, options: { includeStreamingTail: boolean; maxTokens: number | null }): InlineMediaTokenNodePlan[] => {
    const doc = container.ownerDocument;
    if (!doc) {
        return [];
    }
    const plans: InlineMediaTokenNodePlan[] = [];
    let collectedTokens = 0;
    const visitNode = (node: Node): void => {
        if (options.maxTokens !== null && collectedTokens >= options.maxTokens) {
            return;
        }
        if (isElementInOwnDocument(node) && shouldSkipTraversalForElement(node, { includeStreamingTail: options.includeStreamingTail })) {
            return;
        }
        if (isTextInOwnDocument(node)) {
            if (!isTextNodeEligible(node)) {
                return;
            }
            const text = node.nodeValue ?? '';
            PREVIEW_REFERENCE_PATTERN.lastIndex = 0;
            const matches: InlineMediaTokenNodeMatch[] = [];
            for (const rawMatch of text.matchAll(PREVIEW_REFERENCE_PATTERN)) {
                if (options.maxTokens !== null && collectedTokens >= options.maxTokens) {
                    break;
                }
                const token = parsePreviewReferenceTokenMatch(rawMatch);
                if (!token) {
                    continue;
                }
                const startIndex = rawMatch.index;
                if (typeof startIndex !== 'number' || startIndex < 0) {
                    continue;
                }
                matches.push({
                    token,
                    startIndex,
                    endIndex: startIndex + token.raw.length
                });
                collectedTokens += 1;
            }
            if (matches.length <= 0) {
                return;
            }
            plans.push({
                node,
                text,
                matches
            });
            return;
        }
        for (const child of Array.from(node.childNodes)) {
            visitNode(child);
            if (options.maxTokens !== null && collectedTokens >= options.maxTokens) {
                return;
            }
        }
    };
    visitNode(container);
    return plans;
};

const collectInlineMediaTokensInContainer = (container: HTMLElement, options: { maxTokens: number }): InlineMediaToken[] => {
    const maxTokens = clampNumber(options.maxTokens, 0, 50);
    if (maxTokens <= 0) {
        return [];
    }
    const plans = collectInlineMediaTokenNodePlans(container, {
        includeStreamingTail: false,
        maxTokens
    });
    const tokens: InlineMediaToken[] = [];
    for (const plan of plans) {
        for (const match of plan.matches) {
            if (tokens.length >= maxTokens) {
                return tokens;
            }
            tokens.push(match.token);
        }
    }
    return tokens;
};

const replaceInlineMediaTokensWithOptionalRenderer = (container: HTMLElement, options: { includeStreamingTail: boolean; maxTokens: number | null; requireConnectedNodes: boolean; renderToken: InlineMediaOptionalTokenRenderer }): number => {
    const doc = container.ownerDocument;
    if (!doc) {
        return 0;
    }
    const plans = collectInlineMediaTokenNodePlans(container, {
        includeStreamingTail: options.includeStreamingTail,
        maxTokens: options.maxTokens
    });
    let replacedCount = 0;
    for (const plan of plans) {
        const parent = plan.node.parentNode;
        if (!parent || (options.requireConnectedNodes && !plan.node.isConnected)) {
            continue;
        }
        const replacements: InlineMediaTokenNodeReplacement[] = [];
        let hasReplacement = false;
        for (const match of plan.matches) {
            const replacement = options.renderToken(doc, match.token);
            replacements.push({ match, replacement });
            if (replacement) {
                hasReplacement = true;
            }
        }
        if (!hasReplacement) {
            continue;
        }
        let lastIndex = 0;
        for (const item of replacements) {
            const match = item.match;
            if (match.startIndex > lastIndex) {
                parent.insertBefore(doc.createTextNode(plan.text.slice(lastIndex, match.startIndex)), plan.node);
            }
            if (item.replacement) {
                parent.insertBefore(item.replacement, plan.node);
                replacedCount += 1;
            } else {
                parent.insertBefore(doc.createTextNode(plan.text.slice(match.startIndex, match.endIndex)), plan.node);
            }
            lastIndex = match.endIndex;
        }
        if (lastIndex < plan.text.length) {
            parent.insertBefore(doc.createTextNode(plan.text.slice(lastIndex)), plan.node);
        }
        plan.node.remove();
    }
    return replacedCount;
};

const replaceInlineMediaTokensWithRenderer = (container: HTMLElement, options: { includeStreamingTail: boolean; maxTokens: number | null; requireConnectedNodes: boolean; renderToken: InlineMediaTokenRenderer }): number => {
    return replaceInlineMediaTokensWithOptionalRenderer(container, {
        includeStreamingTail: options.includeStreamingTail,
        maxTokens: options.maxTokens,
        requireConnectedNodes: options.requireConnectedNodes,
        renderToken: options.renderToken
    });
};

const replaceInlineMediaTokensInContainer = (container: HTMLElement, options: { includeStreamingTail: boolean; maxTokens: number; requireConnectedNodes: boolean }): number => {
    return replaceInlineMediaTokensWithRenderer(container, {
        includeStreamingTail: options.includeStreamingTail,
        maxTokens: options.maxTokens,
        requireConnectedNodes: options.requireConnectedNodes,
        renderToken: (doc, token) => {
            const routedToken = resolveInlineMultimediaPreviewTokenRoute(token);
            return createInlineMediaPendingCard(doc, {
                type: routedToken.type,
                target: routedToken.target,
                label: routedToken.label,
                raw: routedToken.raw
            });
        }
    });
};

export { collectInlineMediaTokensInContainer, replaceInlineMediaTokensInContainer, replaceInlineMediaTokensWithOptionalRenderer, replaceInlineMediaTokensWithRenderer };
export type { InlineMediaOptionalTokenRenderer, InlineMediaToken, InlineMediaTokenRenderer, InlineMediaTokenType };
