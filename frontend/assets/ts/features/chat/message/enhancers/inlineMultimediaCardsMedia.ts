/* SoAI - Chat feature inline multimedia cards media [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaCardsMedia.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { dom } from '@core/dom/dom.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import type { InlineMediaOpenAction } from '@features/chat/message/enhancers/inlineMultimediaCardTypes.ts';
import { appendInlineMediaDownloadAction, appendInlineMediaSourceActions, createOpenButton } from '@features/chat/message/enhancers/inlineMultimediaCardActions.ts';
import { applyInlineMediaCardSubtitle, buildCardRoot } from '@features/chat/message/enhancers/inlineMultimediaCardLayout.ts';
import { createAudioSlot, createImageSlot, createVideoSlot, resolveMediaAltText } from '@features/chat/message/enhancers/inlineMultimediaMediaSlot.ts';
import { applyChatMultimediaPreviewOpenActionDataset } from '@features/chat/message/multimediaPreviewDataset.ts';

type MediaCardShellOptions = {
    type: 'image' | 'audio' | 'video' | 'embed';
    title: string;
    referenceText: string | null;
    referenceHref: string | null;
    referenceLinkType: string | null;
    openAction: InlineMediaOpenAction;
    downloadHref: string | null;
    sourceHref: string | null;
};

const createMediaCardShell = (doc: Document, options: MediaCardShellOptions): ReturnType<typeof buildCardRoot> => {
    const shell = buildCardRoot(doc, { type: options.type });
    shell.title.textContent = options.title;
    applyInlineMediaCardSubtitle(shell.subtitle, { text: options.referenceText, href: options.referenceHref, externalLinkType: options.referenceLinkType });
    shell.actions.appendChild(createOpenButton(doc, options.openAction, { iconName: 'eye-open' }));
    appendInlineMediaSourceActions(doc, shell.actions, {
        sourceHref: options.sourceHref ?? options.openAction.openSourceUrl,
        referenceHref: options.referenceHref,
        referenceText: options.referenceText,
        referenceLinkType: options.referenceLinkType
    });
    appendInlineMediaDownloadAction(doc, shell.actions, options.downloadHref);
    return shell;
};

const createImageCard = (
    doc: Document,
    options: {
        title: string;
        thumbnailUrl: string;
        referenceText: string | null;
        referenceHref: string | null;
        referenceLinkType: string | null;
        openAction: InlineMediaOpenAction;
        downloadHref: string | null;
    }
): HTMLElement => {
    const shell = createMediaCardShell(doc, { ...options, type: 'image', sourceHref: null });
    const slot = createImageSlot(doc, {
        alt: resolveMediaAltText(options.title, i18n.t('chat.inlinePreviews.imageSubtitle')),
        src: options.thumbnailUrl,
        errorMessage: i18n.t('chat.inlinePreviews.unavailableMessage'),
        typeLabel: shell.root.dataset['mediaTypeLabel'] ?? null
    });
    applyChatMultimediaPreviewOpenActionDataset(slot.slot, options.openAction);
    shell.body.appendChild(slot.slot);
    return shell.root;
};

const createAudioCard = (
    doc: Document,
    options: {
        title: string;
        audioUrl: string;
        referenceText: string | null;
        referenceHref: string | null;
        referenceLinkType: string | null;
        openAction: InlineMediaOpenAction;
        downloadHref: string | null;
    }
): HTMLElement => {
    const shell = createMediaCardShell(doc, { ...options, type: 'audio', sourceHref: null });
    const slot = createAudioSlot(doc, {
        src: options.audioUrl,
        errorMessage: i18n.t('chat.inlinePreviews.unavailableMessage'),
        preload: 'metadata',
        controls: true,
        typeLabel: shell.root.dataset['mediaTypeLabel'] ?? null
    });
    shell.body.appendChild(slot.slot);
    return shell.root;
};

const createVideoCard = (
    doc: Document,
    options: {
        title: string;
        videoUrl: string;
        referenceText: string | null;
        referenceHref: string | null;
        referenceLinkType: string | null;
        openAction: InlineMediaOpenAction;
        downloadHref: string | null;
    }
): HTMLElement => {
    const shell = createMediaCardShell(doc, { ...options, type: 'video', sourceHref: null });
    const slot = createVideoSlot(doc, {
        src: options.videoUrl,
        errorMessage: i18n.t('chat.inlinePreviews.unavailableMessage'),
        preload: 'metadata',
        controls: true,
        typeLabel: shell.root.dataset['mediaTypeLabel'] ?? null
    });
    shell.body.appendChild(slot.slot);
    return shell.root;
};

const createEmbedCard = (
    doc: Document,
    options: {
        title: string;
        thumbnailUrl: string | null;
        referenceText: string | null;
        referenceHref: string | null;
        referenceLinkType: string | null;
        openAction: InlineMediaOpenAction;
        sourceHref: string | null;
    }
): HTMLElement => {
    const shell = createMediaCardShell(doc, { ...options, type: 'embed', downloadHref: null });
    if (options.thumbnailUrl) {
        const slot = createImageSlot(doc, {
            alt: resolveMediaAltText(options.title, i18n.t('chat.inlinePreviews.embedSubtitle')),
            src: options.thumbnailUrl,
            errorMessage: i18n.t('chat.inlinePreviews.unavailableMessage'),
            typeLabel: shell.root.dataset['mediaTypeLabel'] ?? null
        });
        applyChatMultimediaPreviewOpenActionDataset(slot.slot, options.openAction);
        shell.body.appendChild(slot.slot);
    } else {
        const placeholder = doc.createElement('div');
        placeholder.className = 'chat-inline-media-card__media--placeholder';
        placeholder.setAttribute('role', 'note');
        placeholder.setAttribute('aria-label', i18n.t('chat.inlinePreviews.embedPlaceholder'));

        const icon = doc.createElement('span');
        icon.className = 'ui-icon';
        icon.setAttribute('aria-hidden', 'true');
        dom.setHTML(icon, getIconSync('external-link', { size: 18, strokeWidth: 1.5 }), { escape: false });

        const text = doc.createElement('div');
        text.className = 'chat-inline-media-card__media-placeholder-text';
        text.textContent = i18n.t('chat.inlinePreviews.embedPlaceholder');
        placeholder.appendChild(icon);
        placeholder.appendChild(text);
        shell.body.appendChild(placeholder);
    }
    return shell.root;
};

export { createAudioCard, createEmbedCard, createImageCard, createVideoCard };
