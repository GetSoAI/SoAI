/* SoAI - Canonical dataset readers for inline multimedia preview cards [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaCardDataset.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import type { PreviewReferenceToken } from '@features/chat/message/enhancers/inlineMultimediaPreviewContract.ts';

type InlineMediaCardIdentity = {
    tokenType: string | null;
    tokenTarget: string;
    tokenLabel: string | null;
    tokenRaw: string | null;
    remoteUrl: string | null;
};

type InlineMediaCardTokenSnapshot = {
    tokenType: string | null;
    tokenTarget: string;
    tokenLabel: string | null;
    tokenRaw: string | null;
};

const readInlineMediaCardTokenSnapshot = (card: HTMLElement): InlineMediaCardTokenSnapshot => {
    const tokenType = toTrimmedString(card.dataset['inlineMediaTokenType'] ?? '') || null;
    const tokenTarget = toTrimmedString(card.dataset['inlineMediaTokenTarget'] ?? '');
    const tokenLabel = toTrimmedString(card.dataset['inlineMediaTokenLabel'] ?? '') || null;
    const tokenRaw = toTrimmedString(card.dataset['inlineMediaTokenRaw'] ?? '') || null;
    return {
        tokenType,
        tokenTarget,
        tokenLabel,
        tokenRaw
    };
};

const readInlineMediaRemoteUrl = (card: HTMLElement): string => {
    return toTrimmedString(card.dataset['inlineMediaRemoteUrl'] ?? '');
};

const readInlineMediaCardIdentity = (card: HTMLElement): InlineMediaCardIdentity => {
    const tokenSnapshot = readInlineMediaCardTokenSnapshot(card);
    return {
        ...tokenSnapshot,
        remoteUrl: readInlineMediaRemoteUrl(card) || null
    };
};

const applyInlineMediaCardIdentity = (card: HTMLElement, identity: InlineMediaCardIdentity): void => {
    if (identity.tokenType) {
        card.dataset['inlineMediaTokenType'] = identity.tokenType;
    } else {
        delete card.dataset['inlineMediaTokenType'];
    }
    if (identity.tokenTarget) {
        card.dataset['inlineMediaTokenTarget'] = identity.tokenTarget;
    } else {
        delete card.dataset['inlineMediaTokenTarget'];
    }
    card.dataset['inlineMediaTokenLabel'] = identity.tokenLabel ? identity.tokenLabel : '';
    if (identity.tokenRaw) {
        card.dataset['inlineMediaTokenRaw'] = identity.tokenRaw;
    } else {
        delete card.dataset['inlineMediaTokenRaw'];
    }
    if (identity.remoteUrl) {
        card.dataset['inlineMediaRemoteUrl'] = identity.remoteUrl;
    } else {
        delete card.dataset['inlineMediaRemoteUrl'];
    }
};

const encodeInlineMediaIdentityKey = (type: 'token' | 'remote', parts: readonly string[]): string => {
    return JSON.stringify([type, ...parts]);
};

const resolveInlineMediaCardIdentityKey = (identity: InlineMediaCardIdentity): string | null => {
    if (identity.tokenTarget) {
        return encodeInlineMediaIdentityKey('token', [identity.tokenType ?? '', identity.tokenTarget]);
    }
    if (identity.remoteUrl) {
        return encodeInlineMediaIdentityKey('remote', [identity.remoteUrl]);
    }
    return null;
};

const resolveInlineMediaTokenIdentity = (token: PreviewReferenceToken): InlineMediaCardIdentity => {
    return {
        tokenType: token.type,
        tokenTarget: token.target,
        tokenLabel: token.label,
        tokenRaw: token.raw,
        remoteUrl: token.type === 'remote_url' ? token.target : null
    };
};

const resolveInlineMediaRemoteUrlIdentity = (remoteUrl: string): InlineMediaCardIdentity => {
    return {
        tokenType: null,
        tokenTarget: '',
        tokenLabel: null,
        tokenRaw: null,
        remoteUrl
    };
};

const syncInlineMediaRemoteUrlDatasetFromTokenTarget = (card: HTMLElement): void => {
    const tokenTarget = toTrimmedString(card.dataset['inlineMediaTokenTarget'] ?? '');
    if (!tokenTarget) {
        return;
    }
    card.dataset['inlineMediaRemoteUrl'] = tokenTarget;
};

export { applyInlineMediaCardIdentity, readInlineMediaCardIdentity, readInlineMediaCardTokenSnapshot, readInlineMediaRemoteUrl, resolveInlineMediaCardIdentityKey, resolveInlineMediaRemoteUrlIdentity, resolveInlineMediaTokenIdentity, syncInlineMediaRemoteUrlDatasetFromTokenTarget };
export type { InlineMediaCardIdentity, InlineMediaCardTokenSnapshot };
