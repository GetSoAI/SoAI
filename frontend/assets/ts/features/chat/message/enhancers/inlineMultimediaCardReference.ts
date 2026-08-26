/* SoAI - Reference identity resolution for inline multimedia cards [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaCardReference.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readInlineMediaCardTokenSnapshot, type InlineMediaCardIdentity, type InlineMediaCardTokenSnapshot } from '@features/chat/message/enhancers/inlineMultimediaCardDataset.ts';
import { resolveInlineMediaLeafTitle } from '@features/chat/message/enhancers/inlineMultimediaTargetPaths.ts';

interface InlineMediaCardReference {
    label: string;
    rawToken: string;
    failureTarget: string;
    identity: InlineMediaCardIdentity;
}

const resolveInlineMediaCardReference = (card: HTMLElement, target: string, fallbackLabel: string): InlineMediaCardReference => {
    const token = readInlineMediaCardTokenSnapshot(card);
    return resolveInlineMediaCardReferenceFromSnapshot(token, target, fallbackLabel);
};

const resolveInlineMediaCardReferenceFromSnapshot = (token: InlineMediaCardTokenSnapshot, target: string, fallbackLabel: string): InlineMediaCardReference => {
    const resolvedLabel = token.tokenLabel ? token.tokenLabel : target ? resolveInlineMediaLeafTitle(target) : fallbackLabel;
    const rawToken = token.tokenRaw ? token.tokenRaw : target ? target : resolvedLabel;
    return {
        label: resolvedLabel,
        rawToken,
        failureTarget: token.tokenTarget ? token.tokenTarget : rawToken,
        identity: {
            tokenType: token.tokenType,
            tokenTarget: token.tokenTarget,
            tokenLabel: token.tokenLabel,
            tokenRaw: token.tokenRaw,
            remoteUrl: null
        }
    };
};

export { resolveInlineMediaCardReference, resolveInlineMediaCardReferenceFromSnapshot };
export type { InlineMediaCardReference };
