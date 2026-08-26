/* SoAI - Chat feature inline multimedia card layout [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaCardLayout.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { InlineMediaCardType } from '@features/chat/message/enhancers/inlineMultimediaCardTypes.ts';
import { isHTMLAnchorElementInOwnDocument } from '@features/chat/message/enhancers/inlineMultimediaDomSafety.ts';
import { resolveInlineMediaHttpHref } from '@features/chat/message/enhancers/inlineMultimediaUrls.ts';

const truncateText = (value: string, maxChars: number): string => {
    const trimmed = value.trim();
    if (trimmed.length <= maxChars) {
        return trimmed;
    }
    return `${trimmed.slice(0, Math.max(0, maxChars - 1)).trimEnd()}…`;
};

const resolveInlineMediaTypeLabel = (type: InlineMediaCardType): string => {
    if (type === 'pending') {
        return i18n.t('chat.inlinePreviews.typeLabel.preview');
    }
    if (type === 'unavailable') {
        return i18n.t('chat.inlinePreviews.typeLabel.unavailable');
    }
    if (type === 'disabled') {
        return i18n.t('chat.inlinePreviews.typeLabel.reference');
    }
    if (type === 'link') {
        return i18n.t('chat.inlinePreviews.typeLabel.link');
    }
    if (type === 'image') {
        return i18n.t('chat.inlinePreviews.typeLabel.image');
    }
    if (type === 'audio') {
        return i18n.t('chat.inlinePreviews.typeLabel.audio');
    }
    if (type === 'video') {
        return i18n.t('chat.inlinePreviews.typeLabel.video');
    }
    if (type === 'embed') {
        return i18n.t('chat.inlinePreviews.typeLabel.embed');
    }
    if (type === 'text') {
        return i18n.t('chat.inlinePreviews.typeLabel.text');
    }
    if (type === 'document') {
        return i18n.t('chat.inlinePreviews.typeLabel.document');
    }
    if (type === 'folder') {
        return i18n.t('chat.inlinePreviews.typeLabel.folder');
    }
    return i18n.t('chat.inlinePreviews.typeLabel.file');
};

const buildCardRoot = (
    doc: Document,
    options: { type: InlineMediaCardType; isError?: boolean }
): {
    root: HTMLElement;
    footer: HTMLElement;
    title: HTMLElement;
    subtitle: HTMLElement;
    actions: HTMLElement;
    body: HTMLElement;
} => {
    const root = doc.createElement('div');
    root.className = `chat-inline-media-card chat-inline-media-card--${options.type}${options.isError ? ' chat-inline-media-card--error' : ''}`;
    root.dataset['inlineMediaCard'] = '1';
    root.dataset['mediaTypeLabel'] = resolveInlineMediaTypeLabel(options.type);

    const footer = doc.createElement('div');
    footer.className = 'chat-inline-media-card__footer';

    const title = doc.createElement('div');
    title.className = 'chat-inline-media-card__title';

    const subtitle = doc.createElement('div');
    subtitle.className = 'chat-inline-media-card__subtitle';

    const actions = doc.createElement('div');
    actions.className = 'chat-inline-media-card__actions';

    const body = doc.createElement('div');
    body.className = 'chat-inline-media-card__body';

    footer.appendChild(title);
    footer.appendChild(subtitle);
    footer.appendChild(actions);
    root.appendChild(body);
    root.appendChild(footer);
    return { root, footer, title, subtitle, actions, body };
};

const applyInlineMediaCardSubtitle = (
    subtitle: HTMLElement,
    options: {
        text: string | null;
        href: string | null;
        externalLinkType: string | null;
    }
): void => {
    const normalized = options.text ? options.text.trim() : '';
    if (!normalized) {
        subtitle.textContent = '';
        subtitle.hidden = true;
        subtitle.classList.remove('external-link-confirmation');
        delete subtitle.dataset['href'];
        delete subtitle.dataset['externalLinkType'];
        if (isHTMLAnchorElementInOwnDocument(subtitle)) {
            subtitle.removeAttribute('href');
        }
        return;
    }
    subtitle.hidden = false;
    subtitle.textContent = normalized;
    const rawHref = options.href ? options.href.trim() : '';
    if (!rawHref) {
        subtitle.classList.remove('external-link-confirmation');
        delete subtitle.dataset['href'];
        delete subtitle.dataset['externalLinkType'];
        if (isHTMLAnchorElementInOwnDocument(subtitle)) {
            subtitle.removeAttribute('href');
        }
        return;
    }
    const href = resolveInlineMediaHttpHref(rawHref);
    subtitle.classList.add('external-link-confirmation');
    subtitle.dataset['href'] = href;
    if (options.externalLinkType) {
        subtitle.dataset['externalLinkType'] = options.externalLinkType;
    } else {
        delete subtitle.dataset['externalLinkType'];
    }
    if (isHTMLAnchorElementInOwnDocument(subtitle)) {
        subtitle.href = href;
    }
};

export { applyInlineMediaCardSubtitle, buildCardRoot, truncateText };
