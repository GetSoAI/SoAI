/* SoAI - Chat feature inline multimedia card replacement [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaCardReplacement.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { applyInlineMediaCardIdentity, readInlineMediaCardIdentity, resolveInlineMediaCardIdentityKey, type InlineMediaCardIdentity } from '@features/chat/message/enhancers/inlineMultimediaCardDataset.ts';

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

const replaceInlineMediaCardWithIdentity = (card: HTMLElement, replacement: HTMLElement, identity: InlineMediaCardIdentity): boolean => {
    if (!canReplaceInlineMediaCard(card, identity)) {
        return false;
    }
    applyInlineMediaCardIdentity(replacement, identity);
    card.replaceWith(replacement);
    return true;
};

export { replaceInlineMediaCardWithIdentity };
