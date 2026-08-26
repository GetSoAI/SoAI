/* SoAI - Chat feature inline multimedia cards files [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaCardsFiles.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { dom } from '@core/dom/dom.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { CHAT_ACTIONS } from '@features/chat/chatActionIds.ts';
import { appendInlineMediaDownloadAction, appendInlineMediaSourceActions } from '@features/chat/message/enhancers/inlineMultimediaCardActions.ts';
import { applyInlineMediaCardSubtitle, buildCardRoot } from '@features/chat/message/enhancers/inlineMultimediaCardLayout.ts';
import { resolveFileExplorerDeepLinkPath } from '@features/chat/message/enhancers/inlineMultimediaUrls.ts';

const TEXT_FILE_ICON: IconName = 'file-text';
const FOLDER_ICON: IconName = 'folder';

interface InlineMediaFolderEntry {
    name: string;
    isDirectory: boolean;
}

interface InlineMediaFolderPreview {
    entries: readonly InlineMediaFolderEntry[];
    total: number;
}

const createDownloadToViewNotice = (doc: Document): HTMLElement => {
    const message = doc.createElement('div');
    message.className = 'chat-inline-media-card__excerpt chat-inline-media-card__excerpt--download-hint';

    const icon = doc.createElement('span');
    icon.className = 'chat-inline-media-card__excerpt-icon ui-icon';
    icon.setAttribute('aria-hidden', 'true');
    dom.setHTML(icon, getIconSync(TEXT_FILE_ICON, { size: 14, strokeWidth: 1.5 }), { escape: false });

    const text = doc.createElement('span');
    text.className = 'chat-inline-media-card__excerpt-text';
    text.textContent = i18n.t('contentPreview.document.downloadToView');

    message.appendChild(icon);
    message.appendChild(text);
    return message;
};

const createFolderEntryIcon = (doc: Document, iconName: IconName): HTMLElement => {
    const icon = doc.createElement('span');
    icon.className = 'chat-inline-media-card__folder-entry-icon ui-icon';
    icon.setAttribute('aria-hidden', 'true');
    dom.setHTML(icon, getIconSync(iconName, { size: 14, strokeWidth: 1.5 }), { escape: false });
    return icon;
};

const createFolderSummary = (doc: Document, total: number): HTMLElement => {
    const summary = doc.createElement('div');
    summary.className = 'chat-inline-media-card__folder-summary';
    summary.textContent = i18n.plural('chat.inlinePreviews.folderSummary', total, { count: total });
    return summary;
};

const createFolderEntriesList = (doc: Document, preview: InlineMediaFolderPreview): HTMLElement => {
    const list = doc.createElement('div');
    list.className = 'chat-inline-media-card__folder-list';
    if (preview.total <= 0) {
        const empty = doc.createElement('div');
        empty.className = 'chat-inline-media-card__folder-empty';
        empty.textContent = i18n.t('chat.inlinePreviews.folderEmpty');
        list.appendChild(empty);
        return list;
    }
    for (const entry of preview.entries) {
        const row = doc.createElement('div');
        row.className = 'chat-inline-media-card__folder-entry';
        row.appendChild(createFolderEntryIcon(doc, entry.isDirectory ? FOLDER_ICON : TEXT_FILE_ICON));
        const name = doc.createElement('span');
        name.className = 'chat-inline-media-card__folder-entry-name';
        name.textContent = entry.name;
        row.appendChild(name);
        list.appendChild(row);
    }
    const remaining = Math.max(0, preview.total - preview.entries.length);
    if (remaining > 0) {
        const more = doc.createElement('div');
        more.className = 'chat-inline-media-card__folder-more';
        more.textContent = i18n.plural('chat.inlinePreviews.folderMore', remaining, { count: remaining });
        list.appendChild(more);
    }
    return list;
};

const createFolderPreviewButton = (
    doc: Document,
    options: {
        folderPath: string;
        referenceText: string | null;
        preview: InlineMediaFolderPreview;
    }
): HTMLButtonElement => {
    const button = doc.createElement('button');
    button.type = 'button';
    button.className = 'chat-inline-media-card__body chat-inline-media-card__body--folder-preview chat-inline-media-card__excerpt chat-inline-media-card__excerpt--clickable';
    button.dataset.action = CHAT_ACTIONS.OPEN_INLINE_LOCAL_FOLDER;
    button.dataset['inlineMediaFolderPath'] = options.folderPath;
    const referenceText = options.referenceText ? options.referenceText.trim() : '';
    if (referenceText) {
        button.dataset['inlineMediaFolderLabel'] = referenceText;
    }
    button.setAttribute('aria-label', i18n.t('chat.inlinePreviews.openFolderPreview'));
    button.appendChild(createFolderSummary(doc, options.preview.total));
    button.appendChild(createFolderEntriesList(doc, options.preview));
    return button;
};

const createFolderCard = (
    doc: Document,
    options: {
        title: string;
        referenceText: string | null;
        referenceHref: string | null;
        referenceLinkType: string | null;
        openFileExplorerHref: string | null;
        preview: InlineMediaFolderPreview;
    }
): HTMLElement => {
    const folderPath = resolveFileExplorerDeepLinkPath(options.openFileExplorerHref);
    if (!folderPath) {
        throw new Error('Inline folder preview requires a File Explorer folder path');
    }
    const shell = buildCardRoot(doc, { type: 'folder' });
    shell.title.textContent = options.title;
    applyInlineMediaCardSubtitle(shell.subtitle, { text: options.referenceText, href: options.referenceHref, externalLinkType: options.referenceLinkType });
    appendInlineMediaSourceActions(doc, shell.actions, {
        sourceHref: options.openFileExplorerHref,
        referenceHref: options.referenceHref,
        referenceText: options.referenceText,
        referenceLinkType: options.referenceLinkType,
        localFolderAction: {
            folderPath,
            label: options.referenceText
        }
    });
    shell.body.replaceWith(
        createFolderPreviewButton(doc, {
            folderPath,
            referenceText: options.referenceText,
            preview: options.preview
        })
    );
    return shell.root;
};

const createDocumentCard = (
    doc: Document,
    options: {
        title: string;
        referenceText: string | null;
        referenceHref: string | null;
        referenceLinkType: string | null;
        openFileExplorerHref: string | null;
        downloadHref: string | null;
    }
): HTMLElement => {
    return createDownloadableFileCard(doc, { ...options, type: 'document' });
};

const createFileCard = (
    doc: Document,
    options: {
        title: string;
        referenceText: string | null;
        referenceHref: string | null;
        referenceLinkType: string | null;
        openFileExplorerHref: string | null;
        downloadHref: string | null;
    }
): HTMLElement => {
    return createDownloadableFileCard(doc, { ...options, type: 'file' });
};

const createDownloadableFileCard = (
    doc: Document,
    options: {
        type: 'document' | 'file';
        title: string;
        referenceText: string | null;
        referenceHref: string | null;
        referenceLinkType: string | null;
        openFileExplorerHref: string | null;
        downloadHref: string | null;
    }
): HTMLElement => {
    const shell = buildCardRoot(doc, { type: options.type });
    shell.title.textContent = options.title;
    applyInlineMediaCardSubtitle(shell.subtitle, { text: options.referenceText, href: options.referenceHref, externalLinkType: options.referenceLinkType });
    appendInlineMediaSourceActions(doc, shell.actions, {
        sourceHref: options.openFileExplorerHref,
        referenceHref: options.referenceHref,
        referenceText: options.referenceText,
        referenceLinkType: options.referenceLinkType
    });
    appendInlineMediaDownloadAction(doc, shell.actions, options.downloadHref);
    shell.body.classList.add('chat-inline-media-card__body--download-hint');
    shell.body.appendChild(createDownloadToViewNotice(doc));
    return shell.root;
};

export { createDocumentCard, createFileCard, createFolderCard };
export type { InlineMediaFolderEntry, InlineMediaFolderPreview };
