/* SoAI - Chat feature inline multimedia card queries [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaCardQueries.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { readInlineMediaCardTokenSnapshot, readInlineMediaRemoteUrl } from '@features/chat/message/enhancers/inlineMultimediaCardDataset.ts';
import { isHTMLElementInOwnDocument } from '@features/chat/message/enhancers/inlineMultimediaDomSafety.ts';
import type { PreviewReferenceType } from '@features/chat/message/enhancers/inlineMultimediaPreviewContract.ts';

const INLINE_MEDIA_CARD_SELECTOR = '.chat-inline-media-card[data-inline-media-card="1"]';

const isInlineMediaCardElement = (element: Element): element is HTMLElement => {
    return isHTMLElementInOwnDocument(element) && element.matches(INLINE_MEDIA_CARD_SELECTOR);
};

const collectInlineMediaCardElements = (root: HTMLElement): HTMLElement[] => {
    const cards: HTMLElement[] = [];
    if (isInlineMediaCardElement(root)) {
        cards.push(root);
    }
    for (const card of dom.resolveAll(INLINE_MEDIA_CARD_SELECTOR, root)) {
        if (isHTMLElementInOwnDocument(card)) {
            cards.push(card);
        }
    }
    return cards;
};

const hasInlineMediaCards = (root: HTMLElement): boolean => {
    return isInlineMediaCardElement(root) || dom.resolve(INLINE_MEDIA_CARD_SELECTOR, root) !== null;
};

const countInlineMediaCards = (root: HTMLElement): number => {
    return collectInlineMediaCardElements(root).length;
};

const resolvePendingInlineMediaCards = (container: HTMLElement, tokenType: PreviewReferenceType): HTMLElement[] => {
    const selector = `.chat-inline-media-card[data-inline-media-token-type="${tokenType}"][data-inline-media-status="pending"]`;
    return dom.resolveAll(selector, container).filter((card): card is HTMLElement => isHTMLElementInOwnDocument(card) && card.dataset['inlineMediaTokenType'] === tokenType && card.dataset['inlineMediaStatus'] === 'pending');
};

const resolvePendingRemoteUrlInlineMediaCards = (container: HTMLElement): HTMLElement[] => {
    return dom.resolveAll('.chat-inline-media-card[data-inline-media-remote-url][data-inline-media-status="pending"]', container).filter((card): card is HTMLElement => isHTMLElementInOwnDocument(card) && Boolean(readInlineMediaRemoteUrl(card)) && card.dataset['inlineMediaStatus'] === 'pending');
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
