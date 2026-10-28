/* SoAI - Chat feature inline multimedia card replacement [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaCardReplacement.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { animatePresenceMorph, measurePresenceSize, stopPresenceAnimation } from '@core/animations/presence/public.ts';
import { syncElementShell } from '@core/dom/patching.ts';
import { measureLayoutBox, measureLayoutViewport } from '@core/layout/elementGeometry.ts';
import { applyInlineMediaCardIdentity, readInlineMediaCardIdentity, resolveInlineMediaCardIdentityKey, type InlineMediaCardIdentity } from '@features/chat/message/enhancers/inlineMultimediaCardDataset.ts';
import { withAssistantViewportStability } from '@features/chat/message/assistantViewportStability.ts';
import { STREAM_WORD_CLASS } from '@features/chat/stream/streamingTextFadeWrap.ts';

const PRESERVED_CARD_CLASS_NAMES: ReadonlySet<string> = new Set([STREAM_WORD_CLASS]);

const canReplaceInlineMediaCard = (card: HTMLElement, identity: InlineMediaCardIdentity): boolean => {
    if (!card.isConnected) {
        return false;
    }
    if (card.dataset['inlineMediaStatus'] !== 'pending') {
        return false;
    }
    const currentKey = resolveInlineMediaCardIdentityKey(readInlineMediaCardIdentity(card));
    const replacementKey = resolveInlineMediaCardIdentityKey(identity);
    return currentKey !== null && currentKey === replacementKey;
};

const isInsideViewport = (card: HTMLElement): boolean => {
    const view = card.ownerDocument.defaultView;
    if (view === null || card.ownerDocument.visibilityState !== 'visible') {
        return false;
    }
    const bounds = measureLayoutBox(card);
    return bounds.bottom > 0 && bounds.top < measureLayoutViewport(card).height;
};

const resolveInlineMediaCardInPlace = (card: HTMLElement, replacement: HTMLElement): void => {
    const previousSize = isInsideViewport(card) ? measurePresenceSize(card) : null;
    stopPresenceAnimation(card);
    syncElementShell({ target: card, source: replacement, preservedClassNames: PRESERVED_CARD_CLASS_NAMES });
    card.replaceChildren(...Array.from(replacement.childNodes));
    const nextSize = previousSize === null ? null : measurePresenceSize(card);
    if (previousSize !== null && nextSize !== null) {
        animatePresenceMorph(card, previousSize, nextSize, { preserveWrapping: true });
    }
};

const replaceInlineMediaCardWithIdentity = (card: HTMLElement, replacement: HTMLElement, identity: InlineMediaCardIdentity): boolean => {
    if (!canReplaceInlineMediaCard(card, identity)) {
        return false;
    }
    applyInlineMediaCardIdentity(replacement, identity);
    withAssistantViewportStability(card, () => resolveInlineMediaCardInPlace(card, replacement));
    return true;
};

export { replaceInlineMediaCardWithIdentity };
