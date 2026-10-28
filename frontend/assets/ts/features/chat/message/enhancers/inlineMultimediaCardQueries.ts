/* SoAI - Chat feature inline multimedia card queries [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaCardQueries.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { readInlineMediaCardTokenSnapshot, readInlineMediaRemoteUrl } from '@features/chat/message/enhancers/inlineMultimediaCardDataset.ts';
import { isHTMLElementInOwnDocument } from '@features/chat/message/enhancers/inlineMultimediaDomSafety.ts';
import { collectMatchingElements } from '@features/chat/stream/streamDomQueries.ts';
import type { PreviewReferenceType } from '@features/chat/message/enhancers/inlineMultimediaPreviewContract.ts';

const INLINE_MEDIA_CARD_SELECTOR = '.chat-inline-media-card[data-inline-media-card="1"]';

const collectInlineMediaCardElements = (root: HTMLElement): HTMLElement[] => {
    return collectMatchingElements(root, INLINE_MEDIA_CARD_SELECTOR).filter(isHTMLElementInOwnDocument);
};

const hasInlineMediaCards = (root: HTMLElement): boolean => {
    return root.matches(INLINE_MEDIA_CARD_SELECTOR) || dom.resolve(INLINE_MEDIA_CARD_SELECTOR, root) !== null;
};

const countInlineMediaCards = (root: HTMLElement): number => {
    return collectInlineMediaCardElements(root).length;
};

const resolvePendingInlineMediaCards = (container: HTMLElement, tokenType: PreviewReferenceType): HTMLElement[] => {
    const selector = `.chat-inline-media-card[data-inline-media-token-type="${tokenType}"][data-inline-media-status="pending"]`;
    return collectMatchingElements(container, selector).filter(isHTMLElementInOwnDocument);
};

const resolvePendingRemoteUrlInlineMediaCards = (container: HTMLElement): HTMLElement[] => {
    return collectMatchingElements(container, '.chat-inline-media-card[data-inline-media-remote-url][data-inline-media-status="pending"]').filter((card) => isHTMLElementInOwnDocument(card) && Boolean(readInlineMediaRemoteUrl(card)));
};

const groupPendingInlineMediaCardsByTarget = (pendingCards: readonly HTMLElement[]): { targets: string[]; cardsByTarget: Map<string, HTMLElement[]> } => {
    const targets: string[] = [];
    const cardsByTarget = new Map<string, HTMLElement[]>();
    for (const card of pendingCards) {
        const token = readInlineMediaCardTokenSnapshot(card);
        const target = token.tokenTarget;
        if (!target) {
            continue;
        }
        const existing = cardsByTarget.get(target);
        if (existing) {
            existing.push(card);
            continue;
        }
        cardsByTarget.set(target, [card]);
        targets.push(target);
    }
    return { targets, cardsByTarget };
};

export { collectInlineMediaCardElements, countInlineMediaCards, groupPendingInlineMediaCardsByTarget, hasInlineMediaCards, resolvePendingInlineMediaCards, resolvePendingRemoteUrlInlineMediaCards };
