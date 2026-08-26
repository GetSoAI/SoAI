/* SoAI - Chat feature assistant DOM state [frontend/assets/ts/features/chat/message/assistantDomState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { collectMarkdownTableSortState, hasMarkdownTableSortState, restoreMarkdownTableSortState, type MarkdownTableSortState } from '@features/chat/message/assistantMarkdownTableSortState.ts';
import { collectInlineMediaCardPreservation, discardInlineMediaCardsFromPreservation, type InlineMediaCardPreservation } from '@features/chat/message/assistantInlineMediaCardPreservation.ts';
import { hasInlineMediaCards } from '@features/chat/message/enhancers/inlineMultimediaCardQueries.ts';
import { buildInlineActivityDetailsDomKey, commitPreservedInlineActivityDetailsRoot, shouldPreserveInlineActivityDetailsRoot } from '@features/chat/message/inlineActivityDetailsLifecycle.ts';
import { resolveDirectInlineActivityDetailsRoot } from '@features/chat/message/inlineActivityDetailsIdentity.ts';
import { applyCollapsedActivityState, readCollapsedActivityState } from '@features/chat/stream/streamCollapsedActivityState.ts';
import { collectMermaidContainersByKey, restoreMermaidContainersByKey } from '@features/chat/stream/streamDomCache.ts';
import { collectMatchingElements } from '@features/chat/stream/streamDomQueries.ts';
import { applyKeyedScrollableState, readKeyedScrollableState } from '@features/chat/stream/streamScrollableState.ts';

type AssistantDomStatePreservation = {
    collapsedActivityState: Map<string, boolean>;
    expandedActivityDetails: Map<string, HTMLElement>;
    inlineMediaCards: InlineMediaCardPreservation;
    mermaidContainers: Map<string, HTMLElement[]>;
    scrollState: ReturnType<typeof readKeyedScrollableState>;
    markdownTableSortState: MarkdownTableSortState;
};

const collectExpandedActivityDetails = (root: Element): Map<string, HTMLElement> => {
    const preserved = new Map<string, HTMLElement>();
    for (const element of collectMatchingElements(root, '.inline-activity[data-call-id][data-collapsed="false"]')) {
        const key = buildInlineActivityDetailsDomKey(element);
        if (key === null || preserved.has(key)) {
            continue;
        }
        const details = resolveDirectInlineActivityDetailsRoot(element);
        if (shouldPreserveInlineActivityDetailsRoot(element, details)) {
            preserved.set(key, details);
        }
    }
    return preserved;
};

const restoreExpandedActivityDetails = (root: Element, preserved: ReadonlyMap<string, HTMLElement>): void => {
    if (preserved.size === 0) {
        return;
    }
    for (const element of collectMatchingElements(root, '.inline-activity[data-call-id]')) {
        if (element.getAttribute('data-collapsed') === 'true') {
            continue;
        }
        const key = buildInlineActivityDetailsDomKey(element);
        if (key === null || !preserved.has(key) || resolveDirectInlineActivityDetailsRoot(element)) {
            continue;
        }
        const details = preserved.get(key);
        if (details instanceof HTMLElement) {
            commitPreservedInlineActivityDetailsRoot(element, details);
        }
    }
};

const collectAssistantDomState = (root: HTMLElement): AssistantDomStatePreservation => {
    return {
        collapsedActivityState: readCollapsedActivityState(root),
        expandedActivityDetails: collectExpandedActivityDetails(root),
        inlineMediaCards: collectInlineMediaCardPreservation(root),
        mermaidContainers: collectMermaidContainersByKey(root),
        scrollState: readKeyedScrollableState(root),
        markdownTableSortState: collectMarkdownTableSortState(root)
    };
};

const hasPreservableAssistantDomState = (root: HTMLElement): boolean => {
    return hasInlineMediaCards(root) || hasMarkdownTableSortState(root) || root.matches('.inline-activity[data-call-id][data-collapsed], .mermaid-container, [data-scroll-key]') || dom.resolve('.inline-activity[data-call-id][data-collapsed], .mermaid-container, [data-scroll-key]', root) !== null;
};

const resolveAssistantDomStateForPatch = (root: HTMLElement, state: AssistantDomStatePreservation | null): AssistantDomStatePreservation | null => {
    if (state !== null) {
        return state;
    }
    return hasPreservableAssistantDomState(root) ? collectAssistantDomState(root) : null;
};

const restoreAssistantDomState = (root: HTMLElement, state: AssistantDomStatePreservation): void => {
    applyCollapsedActivityState(root, state.collapsedActivityState);
    restoreExpandedActivityDetails(root, state.expandedActivityDetails);
    restoreMermaidContainersByKey(root, state.mermaidContainers);
    restoreMarkdownTableSortState(root, state.markdownTableSortState);
    if (state.scrollState !== null) {
        applyKeyedScrollableState(root, state.scrollState);
    }
};

const discardInlineMediaCardsFromAssistantDomState = (root: HTMLElement, state: AssistantDomStatePreservation): void => {
    discardInlineMediaCardsFromPreservation(root, state.inlineMediaCards);
};

export { collectAssistantDomState, discardInlineMediaCardsFromAssistantDomState, resolveAssistantDomStateForPatch, restoreAssistantDomState };
export type { AssistantDomStatePreservation };
