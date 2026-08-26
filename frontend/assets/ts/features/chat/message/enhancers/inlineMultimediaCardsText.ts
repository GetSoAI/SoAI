/* SoAI - Chat feature inline multimedia cards text [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaCardsText.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { InlineMediaOpenAction } from '@features/chat/message/enhancers/inlineMultimediaCardTypes.ts';
import { appendInlineMediaSourceActions, createOpenButton } from '@features/chat/message/enhancers/inlineMultimediaCardActions.ts';
import { applyInlineMediaCardSubtitle, buildCardRoot, truncateText } from '@features/chat/message/enhancers/inlineMultimediaCardLayout.ts';
import { createImageSlot, resolveMediaAltText } from '@features/chat/message/enhancers/inlineMultimediaMediaSlot.ts';
import { resolveInlineMediaHttpHref } from '@features/chat/message/enhancers/inlineMultimediaUrls.ts';
import { applyChatMultimediaPreviewOpenActionDataset } from '@features/chat/message/multimediaPreviewDataset.ts';

const MAX_EXCERPT_CHARS = 260;

const normalizeComparableExcerptText = (value: string): string => {
    return toTrimmedString(value).replace(/\s+/g, ' ').toLocaleLowerCase();
};

const createExcerptElement = (doc: Document, excerptText: string): HTMLDivElement => {
    const excerpt = doc.createElement('div');
    excerpt.className = 'chat-inline-media-card__excerpt';
    excerpt.textContent = truncateText(excerptText, MAX_EXCERPT_CHARS);
    return excerpt;
};

const createClickableTextExcerpt = (doc: Document, excerptText: string, openAction: InlineMediaOpenAction): HTMLButtonElement => {
    const excerpt = doc.createElement('button');
    excerpt.type = 'button';
    excerpt.className = 'chat-inline-media-card__excerpt chat-inline-media-card__excerpt--clickable';
    excerpt.textContent = truncateText(excerptText, MAX_EXCERPT_CHARS);
    applyChatMultimediaPreviewOpenActionDataset(excerpt, openAction);
    excerpt.setAttribute('aria-label', i18n.t('common.view'));
    return excerpt;
};

const createTextCard = (
    doc: Document,
    options: {
        title: string;
        referenceText: string | null;
        referenceHref: string | null;
        referenceLinkType: string | null;
        excerpt: string;
        openAction: InlineMediaOpenAction;
        sourceHref: string | null;
    }
): HTMLElement => {
    const shell = buildCardRoot(doc, { type: 'text' });
    shell.title.textContent = options.title;
    applyInlineMediaCardSubtitle(shell.subtitle, { text: options.referenceText, href: options.referenceHref, externalLinkType: options.referenceLinkType });
    shell.actions.appendChild(createOpenButton(doc, options.openAction, { iconName: 'eye-open' }));
    appendInlineMediaSourceActions(doc, shell.actions, {
        sourceHref: options.sourceHref,
        referenceHref: options.referenceHref,
        referenceText: options.referenceText,
        referenceLinkType: options.referenceLinkType
    });
    shell.body.appendChild(createClickableTextExcerpt(doc, options.excerpt, options.openAction));
    return shell.root;
};

const createLinkCard = (
    doc: Document,
    options: {
        title: string;
        referenceText: string | null;
        referenceHref: string | null;
        referenceLinkType: string | null;
        description: string | null;
        thumbnailUrl: string | null;
        excerpt: string;
        sourceHref: string | null;
    }
): HTMLElement => {
    const shell = buildCardRoot(doc, { type: 'link' });
    shell.title.textContent = options.title;
    applyInlineMediaCardSubtitle(shell.subtitle, { text: options.referenceText, href: options.referenceHref, externalLinkType: options.referenceLinkType });
    appendInlineMediaSourceActions(doc, shell.actions, {
        sourceHref: options.sourceHref,
        referenceHref: options.referenceHref,
        referenceText: options.referenceText,
        referenceLinkType: options.referenceLinkType
    });
    if (options.thumbnailUrl) {
        const slot = createImageSlot(doc, {
            alt: resolveMediaAltText(options.title, i18n.t('chat.inlinePreviews.linkSubtitle')),
            src: options.thumbnailUrl,
            errorMessage: i18n.t('chat.inlinePreviews.unavailableMessage'),
            typeLabel: shell.root.dataset['mediaTypeLabel'] ?? null
        });
        if (options.sourceHref) {
            slot.slot.dataset['externalLinkType'] = 'chat-link';
            slot.slot.classList.add('external-link-confirmation');
            slot.slot.dataset['href'] = resolveInlineMediaHttpHref(options.sourceHref);
        }
        shell.body.appendChild(slot.slot);
    }
    const descriptionText = options.description ? truncateText(options.description, 240) : '';
    if (descriptionText) {
        shell.body.appendChild(createExcerptElement(doc, descriptionText));
    }
    const excerptText = truncateText(options.excerpt, MAX_EXCERPT_CHARS);
    if (excerptText && normalizeComparableExcerptText(options.excerpt) !== normalizeComparableExcerptText(options.title)) {
        shell.body.appendChild(createExcerptElement(doc, excerptText));
    }
    return shell.root;
};

export { createLinkCard, createTextCard };
