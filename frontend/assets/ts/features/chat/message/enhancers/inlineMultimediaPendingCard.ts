/* SoAI - Canonical pending inline preview shell creation [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaPendingCard.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { createPendingCard } from '@features/chat/message/enhancers/inlineMultimediaCardsStatus.ts';
import type { PreviewReferenceType } from '@features/chat/message/enhancers/inlineMultimediaPreviewContract.ts';
import { resolveInlineMultimediaReferenceTitle } from '@features/chat/message/enhancers/inlineMultimediaReferenceTitle.ts';

interface InlineMediaPendingCardDescriptor {
    type: PreviewReferenceType | null;
    target: string;
    label: string | null;
    raw: string | null;
}

interface InlineMediaPendingCardMarkupHost {
    escapeHtml: (unsafe: string) => string;
    escapeAttribute: (value: string) => string;
}

const resolvePendingCardTitle = (descriptor: InlineMediaPendingCardDescriptor): string => {
    const referenceTitle = resolveInlineMultimediaReferenceTitle(descriptor);
    if (referenceTitle !== null) {
        return referenceTitle;
    }
    if (toTrimmedString(descriptor.target)) {
        return i18n.t('chat.inlinePreviews.pendingTitle');
    }
    return i18n.t('common.loading');
};

const applyPendingCardMetadata = (card: HTMLElement, descriptor: InlineMediaPendingCardDescriptor): void => {
    card.dataset['inlineMediaStatus'] = 'pending';
    if (descriptor.type) {
        card.dataset['inlineMediaTokenType'] = descriptor.type;
    } else {
        delete card.dataset['inlineMediaTokenType'];
    }
    if (descriptor.target) {
        card.dataset['inlineMediaTokenTarget'] = descriptor.target;
    } else {
        delete card.dataset['inlineMediaTokenTarget'];
    }
    if (descriptor.type === 'remote_url' && descriptor.target) {
        card.dataset['inlineMediaRemoteUrl'] = descriptor.target;
    } else {
        delete card.dataset['inlineMediaRemoteUrl'];
    }
    if (descriptor.raw) {
        card.dataset['inlineMediaTokenRaw'] = descriptor.raw;
    } else {
        delete card.dataset['inlineMediaTokenRaw'];
    }
    card.dataset['inlineMediaTokenLabel'] = descriptor.label ? descriptor.label : '';
};

const renderOptionalDataAttribute = (host: InlineMediaPendingCardMarkupHost, name: string, value: string | null): string => {
    if (!value) {
        return '';
    }
    return ` ${name}="${host.escapeAttribute(value)}"`;
};

const renderInlineMediaPendingCardHtml = (host: InlineMediaPendingCardMarkupHost, descriptor: InlineMediaPendingCardDescriptor): string => {
    const mediaTypeLabel = host.escapeAttribute(i18n.t('chat.inlinePreviews.typeLabel.preview'));
    const title = host.escapeHtml(resolvePendingCardTitle(descriptor));
    const subtitle = host.escapeHtml(i18n.t('common.loading'));
    const typeAttribute = renderOptionalDataAttribute(host, 'data-inline-media-token-type', descriptor.type);
    const targetAttribute = renderOptionalDataAttribute(host, 'data-inline-media-token-target', descriptor.target);
    const remoteUrlAttribute = descriptor.type === 'remote_url' ? renderOptionalDataAttribute(host, 'data-inline-media-remote-url', descriptor.target) : '';
    const rawAttribute = renderOptionalDataAttribute(host, 'data-inline-media-token-raw', descriptor.raw);
    const labelAttribute = ` data-inline-media-token-label="${host.escapeAttribute(descriptor.label ? descriptor.label : '')}"`;
    return `<div class="chat-inline-media-card chat-inline-media-card--pending" data-inline-media-card="1" data-media-type-label="${mediaTypeLabel}" data-inline-media-status="pending"${typeAttribute}${targetAttribute}${remoteUrlAttribute}${rawAttribute}${labelAttribute}><div class="chat-inline-media-card__body"><span class="loading-spinner" aria-hidden="true"></span></div><div class="chat-inline-media-card__footer"><div class="chat-inline-media-card__title">${title}</div><div class="chat-inline-media-card__subtitle">${subtitle}</div><div class="chat-inline-media-card__actions"></div></div></div>`;
};

const createInlineMediaPendingCard = (doc: Document, descriptor: InlineMediaPendingCardDescriptor): HTMLElement => {
    const card = createPendingCard(doc, resolvePendingCardTitle(descriptor));
    applyPendingCardMetadata(card, descriptor);
    return card;
};

export { createInlineMediaPendingCard, renderInlineMediaPendingCardHtml };
export type { InlineMediaPendingCardDescriptor, InlineMediaPendingCardMarkupHost };
