/* SoAI - Chat feature assistant inline media card preservation [frontend/assets/ts/features/chat/message/assistantInlineMediaCardPreservation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { isAbsoluteHttpUrl } from '@core/security/public.ts';
import { applyInlineMediaCardIdentity, readInlineMediaCardIdentity, resolveInlineMediaCardIdentityKey, resolveInlineMediaRemoteUrlIdentity, resolveInlineMediaTokenIdentity, type InlineMediaCardIdentity } from '@features/chat/message/enhancers/inlineMultimediaCardDataset.ts';
import { collectInlineMediaCardElements } from '@features/chat/message/enhancers/inlineMultimediaCardQueries.ts';
import { resolveEligibleInlineMediaRemoteAnchorHref } from '@features/chat/message/enhancers/inlineMultimediaDomSafety.ts';
import { createInlineMediaPendingCard } from '@features/chat/message/enhancers/inlineMultimediaPendingCard.ts';
import { replaceInlineMediaTokensWithOptionalRenderer, type InlineMediaToken } from '@features/chat/message/enhancers/inlineMultimediaTokenParsing.ts';

type InlineMediaCardPreservation = {
    cardsByIdentity: Map<string, HTMLElement[]>;
};
type RemoteAnchorCardResolver = (identityKey: string | null) => HTMLElement | null;

const isRemoteUrl = (value: string | null): value is string => isAbsoluteHttpUrl(value);

const resolveInlineMediaCardIdentityKeys = (identity: InlineMediaCardIdentity): string[] => {
    const keys: string[] = [];
    const primaryKey = resolveInlineMediaCardIdentityKey(identity);
    if (primaryKey) {
        keys.push(primaryKey);
    }
    const remoteTarget = isRemoteUrl(identity.remoteUrl) ? identity.remoteUrl : identity.tokenType === 'remote_url' && isRemoteUrl(identity.tokenTarget) ? identity.tokenTarget : null;
    if (remoteTarget) {
        const remoteKey = resolveInlineMediaCardIdentityKey(resolveInlineMediaRemoteUrlIdentity(remoteTarget));
        if (remoteKey && !keys.includes(remoteKey)) {
            keys.push(remoteKey);
        }
    }
    return keys;
};

const collectInlineMediaCardPreservation = (root: HTMLElement): InlineMediaCardPreservation => {
    const preservation: InlineMediaCardPreservation = {
        cardsByIdentity: new Map()
    };
    for (const card of collectInlineMediaCardElements(root)) {
        for (const identityKey of resolveInlineMediaCardIdentityKeys(readInlineMediaCardIdentity(card))) {
            const queue = preservation.cardsByIdentity.get(identityKey);
            if (queue) {
                queue.push(card);
                continue;
            }
            preservation.cardsByIdentity.set(identityKey, [card]);
        }
    }
    return preservation;
};

const removeInlineMediaCardFromQueues = (preservation: InlineMediaCardPreservation, card: HTMLElement): void => {
    for (const identityKey of resolveInlineMediaCardIdentityKeys(readInlineMediaCardIdentity(card))) {
        const queue = preservation.cardsByIdentity.get(identityKey) ?? null;
        if (!queue) {
            continue;
        }
        const index = queue.indexOf(card);
        if (index < 0) {
            continue;
        }
        queue.splice(index, 1);
        if (queue.length === 0) {
            preservation.cardsByIdentity.delete(identityKey);
        }
    }
};

const consumePreservedInlineMediaCard = (preservation: InlineMediaCardPreservation, identityKey: string | null): HTMLElement | null => {
    if (!identityKey) {
        return null;
    }
    const queue = preservation.cardsByIdentity.get(identityKey) ?? null;
    if (!queue || queue.length <= 0) {
        return null;
    }
    while (queue.length > 0) {
        const card = queue.shift() ?? null;
        if (!card) {
            continue;
        }
        removeInlineMediaCardFromQueues(preservation, card);
        if (queue.length === 0) {
            preservation.cardsByIdentity.delete(identityKey);
        }
        if (!card.isConnected) {
            continue;
        }
        return card;
    }
    preservation.cardsByIdentity.delete(identityKey);
    return null;
};

const consumePreservedInlineMediaCardByIdentity = (preservation: InlineMediaCardPreservation, identity: InlineMediaCardIdentity): HTMLElement | null => {
    for (const identityKey of resolveInlineMediaCardIdentityKeys(identity)) {
        const card = consumePreservedInlineMediaCard(preservation, identityKey);
        if (card) {
            return card;
        }
    }
    return null;
};

const discardInlineMediaCardsFromPreservation = (root: HTMLElement, preservation: InlineMediaCardPreservation): void => {
    for (const card of collectInlineMediaCardElements(root)) {
        removeInlineMediaCardFromQueues(preservation, card);
    }
};

const replaceNodeWithPreservedInlineMediaCard = (target: Node, preservedCard: HTMLElement): void => {
    const parent = target.parentNode;
    if (!parent) {
        throw new Error('Inline media card preservation requires an attached replacement target.');
    }
    parent.insertBefore(preservedCard, target);
    parent.removeChild(target);
};

const cloneInlineMediaCard = (card: HTMLElement): HTMLElement => {
    const cloned = card.cloneNode(true);
    if (!(cloned instanceof HTMLElement)) {
        throw new Error('Inline media card preservation failed to clone a card element.');
    }
    return cloned;
};

const cloneInlineMediaCardPreservation = (preservation: InlineMediaCardPreservation): InlineMediaCardPreservation => {
    const cloned: InlineMediaCardPreservation = {
        cardsByIdentity: new Map()
    };
    for (const [identityKey, cards] of preservation.cardsByIdentity.entries()) {
        cloned.cardsByIdentity.set(identityKey, [...cards]);
    }
    return cloned;
};

const consumePreservedInlineMediaCardCloneByIdentity = (preservation: InlineMediaCardPreservation, identity: InlineMediaCardIdentity): HTMLElement | null => {
    const card = consumePreservedInlineMediaCardByIdentity(preservation, identity);
    return card ? cloneInlineMediaCard(card) : null;
};

const restoreRenderedInlineMediaCards = (container: HTMLElement, preservation: InlineMediaCardPreservation): void => {
    for (const card of collectInlineMediaCardElements(container)) {
        const preservedCard = consumePreservedInlineMediaCardByIdentity(preservation, readInlineMediaCardIdentity(card));
        if (!preservedCard || preservedCard === card) {
            continue;
        }
        replaceNodeWithPreservedInlineMediaCard(card, preservedCard);
    }
};

const cloneRenderedInlineMediaCards = (container: HTMLElement, preservation: InlineMediaCardPreservation): void => {
    for (const card of collectInlineMediaCardElements(container)) {
        const preservedCard = consumePreservedInlineMediaCardCloneByIdentity(preservation, readInlineMediaCardIdentity(card));
        if (!preservedCard) {
            continue;
        }
        replaceNodeWithPreservedInlineMediaCard(card, preservedCard);
    }
};

const restoreInlineMediaTokens = (container: HTMLElement, preservation: InlineMediaCardPreservation): void => {
    replaceInlineMediaTokensWithOptionalRenderer(container, {
        includeStreamingTail: false,
        maxTokens: null,
        requireConnectedNodes: true,
        renderToken: (doc, token) => {
            return consumePreservedInlineMediaCardByIdentity(preservation, resolveInlineMediaTokenIdentity(token)) ?? renderMissingPreservedInlineMediaToken(doc, token);
        }
    });
};

const renderMissingPreservedInlineMediaToken = (doc: Document, token: InlineMediaToken): HTMLElement => {
    return createInlineMediaPendingCard(doc, {
        type: token.type,
        target: token.target,
        label: token.label,
        raw: token.raw
    });
};

const cloneInlineMediaTokens = (container: HTMLElement, preservation: InlineMediaCardPreservation): void => {
    replaceInlineMediaTokensWithOptionalRenderer(container, {
        includeStreamingTail: false,
        maxTokens: null,
        requireConnectedNodes: false,
        renderToken: (_doc, token) => consumePreservedInlineMediaCardCloneByIdentity(preservation, resolveInlineMediaTokenIdentity(token))
    });
};

const replacePreservedInlineMediaRemoteAnchors = (container: HTMLElement, resolveCard: RemoteAnchorCardResolver): void => {
    const anchors = dom.resolveAll('a[href]', container);
    for (const anchor of anchors) {
        if (!(anchor instanceof HTMLAnchorElement)) {
            continue;
        }
        const href = resolveEligibleInlineMediaRemoteAnchorHref(anchor);
        if (href === null) {
            continue;
        }
        const preservedCard = resolveCard(resolveInlineMediaCardIdentityKey(resolveInlineMediaRemoteUrlIdentity(href)));
        if (!preservedCard) {
            continue;
        }
        applyInlineMediaCardIdentity(preservedCard, {
            tokenType: null,
            tokenTarget: '',
            tokenLabel: null,
            tokenRaw: null,
            remoteUrl: href
        });
        replaceNodeWithPreservedInlineMediaCard(anchor, preservedCard);
    }
};

const restoreInlineMediaCardsFromPreservation = (container: HTMLElement, preservation: InlineMediaCardPreservation): void => {
    if (preservation.cardsByIdentity.size <= 0) {
        return;
    }
    restoreRenderedInlineMediaCards(container, preservation);
    restoreInlineMediaTokens(container, preservation);
    replacePreservedInlineMediaRemoteAnchors(container, (identityKey) => consumePreservedInlineMediaCard(preservation, identityKey));
};

const cloneInlineMediaCardsIntoPreservedPositions = (container: HTMLElement, preservation: InlineMediaCardPreservation): void => {
    if (preservation.cardsByIdentity.size <= 0) {
        return;
    }
    const clonedPreservation = cloneInlineMediaCardPreservation(preservation);
    cloneRenderedInlineMediaCards(container, clonedPreservation);
    cloneInlineMediaTokens(container, clonedPreservation);
    replacePreservedInlineMediaRemoteAnchors(container, (identityKey) => {
        const card = consumePreservedInlineMediaCard(clonedPreservation, identityKey);
        return card ? cloneInlineMediaCard(card) : null;
    });
};

export { cloneInlineMediaCardsIntoPreservedPositions, collectInlineMediaCardPreservation, discardInlineMediaCardsFromPreservation, restoreInlineMediaCardsFromPreservation };
export type { InlineMediaCardPreservation };
