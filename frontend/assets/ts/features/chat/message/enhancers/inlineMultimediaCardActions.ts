/* SoAI - Chat feature inline multimedia card actions [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaCardActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { dom } from '@core/dom/dom.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { CHAT_ACTIONS } from '@features/chat/chatActionIds.ts';
import { applyChatMultimediaPreviewOpenActionDataset } from '@features/chat/message/multimediaPreviewDataset.ts';
import type { InlineMediaOpenAction } from '@features/chat/message/enhancers/inlineMultimediaCardTypes.ts';
import { resolveInlineMediaHttpHref } from '@features/chat/message/enhancers/inlineMultimediaUrls.ts';

type InlineMediaLinkType = 'download' | 'external' | 'internal';
type InlineMediaLocalFolderAction = {
    folderPath: string;
    label: string | null;
};
type InlineMediaCopyValueOptions = {
    sourceHref: string | null;
    referenceHref: string | null;
    referenceText: string | null;
    referenceLinkType: string | null;
    localFolderAction?: InlineMediaLocalFolderAction | null;
};

const setLabeledActionAttributes = (element: HTMLAnchorElement | HTMLButtonElement, label: string): void => {
    element.setAttribute('aria-label', label);
    setTooltipText(element, label);
};

const appendActionIcon = (doc: Document, element: HTMLAnchorElement | HTMLButtonElement, iconName: IconName): void => {
    const icon = doc.createElement('span');
    icon.className = 'ui-icon';
    icon.setAttribute('aria-hidden', 'true');
    dom.setHTML(icon, getIconSync(iconName, { size: 14, strokeWidth: 1.5 }), { escape: false });
    element.appendChild(icon);
};

const createOpenButton = (doc: Document, action: InlineMediaOpenAction, options: { iconName?: IconName } = {}): HTMLButtonElement => {
    const button = doc.createElement('button');
    button.type = 'button';
    button.className = 'ui-icon-button ui-icon-button-small ui-variant-neutral chat-inline-media-card__action chat-inline-media-card__action--icon chat-inline-media-card__open';
    applyChatMultimediaPreviewOpenActionDataset(button, action);
    const label = i18n.t('common.view');
    setLabeledActionAttributes(button, label);
    appendActionIcon(doc, button, options.iconName ?? 'external-link');
    return button;
};

const createLinkAction = (
    doc: Document,
    options: {
        href: string;
        label: string;
        className?: string;
        linkType?: InlineMediaLinkType;
        iconName?: IconName;
    }
): HTMLAnchorElement => {
    const link = doc.createElement('a');
    const linkType = options.linkType ?? 'internal';
    const trimmedHref = options.href.trim();
    const resolvedHref = linkType === 'internal' && trimmedHref.startsWith('#') ? trimmedHref : resolveInlineMediaHttpHref(trimmedHref);
    link.className = ['ui-icon-button ui-icon-button-small ui-variant-neutral chat-inline-media-card__action chat-inline-media-card__action--icon', options.className ?? ''].filter((value) => value.trim().length > 0).join(' ');
    link.href = resolvedHref;
    setLabeledActionAttributes(link, options.label);
    appendActionIcon(doc, link, options.iconName ?? 'external-link');
    if (linkType === 'download') {
        link.setAttribute('download', '');
        link.dataset.action = CHAT_ACTIONS.DOWNLOAD_MULTIMEDIA;
    }
    if (linkType === 'external') {
        link.classList.add('external-link-confirmation');
        link.dataset['href'] = resolvedHref;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
    }
    return link;
};

const createOpenSourceAction = (doc: Document, href: string): HTMLAnchorElement => {
    const normalizedHref = href.trim();
    const label = i18n.t('contentPreview.actions.openSource');
    const resolvedHref = resolveInlineMediaHttpHref(normalizedHref);
    const linkType = normalizedHref.startsWith('#fileExplorer?') ? 'chat-path' : null;

    const link = doc.createElement('a');
    link.className = 'ui-icon-button ui-icon-button-small ui-variant-neutral chat-inline-media-card__action chat-inline-media-card__action--icon external-link-confirmation';
    link.href = normalizedHref;
    link.dataset['href'] = resolvedHref;
    if (linkType) {
        link.dataset['externalLinkType'] = linkType;
    }
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    setLabeledActionAttributes(link, label);
    appendActionIcon(doc, link, 'external-link');
    return link;
};

const createOpenLocalFolderAction = (doc: Document, action: InlineMediaLocalFolderAction): HTMLButtonElement => {
    const button = doc.createElement('button');
    button.type = 'button';
    button.className = 'ui-icon-button ui-icon-button-small ui-variant-neutral chat-inline-media-card__action chat-inline-media-card__action--icon';
    button.dataset.action = CHAT_ACTIONS.OPEN_INLINE_LOCAL_FOLDER;
    button.dataset['inlineMediaFolderPath'] = action.folderPath;
    const label = action.label ? action.label.trim() : '';
    if (label) {
        button.dataset['inlineMediaFolderLabel'] = label;
    }
    setLabeledActionAttributes(button, i18n.t('chat.inlinePreviews.openFolderPreview'));
    appendActionIcon(doc, button, 'external-link');
    return button;
};

const resolveInlineMediaCopyValue = (options: InlineMediaCopyValueOptions): string => {
    const sourceHref = options.sourceHref ? options.sourceHref.trim() : '';
    const referenceHref = options.referenceHref ? options.referenceHref.trim() : '';
    const referenceText = options.referenceText ? options.referenceText.trim() : '';
    if (options.referenceLinkType === 'chat-path' && referenceText) {
        return referenceText;
    }
    if (sourceHref) {
        return sourceHref;
    }
    if (referenceHref) {
        return referenceHref;
    }
    return referenceText;
};

const appendInlineMediaSourceActions = (doc: Document, actions: HTMLElement, options: InlineMediaCopyValueOptions): void => {
    const openSourceHref = options.sourceHref ? options.sourceHref.trim() : options.referenceHref ? options.referenceHref.trim() : '';
    const copyValue = resolveInlineMediaCopyValue(options);
    if (openSourceHref) {
        const openAction = options.localFolderAction ? createOpenLocalFolderAction(doc, options.localFolderAction) : createOpenSourceAction(doc, openSourceHref);
        actions.appendChild(openAction);
    }
    if (copyValue) {
        actions.appendChild(createCopyButton(doc, copyValue));
    }
};

const appendInlineMediaDownloadAction = (doc: Document, actions: HTMLElement, downloadHref: string | null): void => {
    if (!downloadHref) {
        return;
    }
    actions.appendChild(
        createLinkAction(doc, {
            href: downloadHref,
            label: i18n.t('fileExplorer.modal.download'),
            linkType: 'download',
            iconName: 'download'
        })
    );
};

const createCopyButton = (doc: Document, value: string): HTMLButtonElement => {
    const button = doc.createElement('button');
    button.type = 'button';
    const label = i18n.t('common.copy');
    button.className = 'code-copy-btn ui-icon-button ui-icon-button-small ui-variant-neutral chat-inline-media-card__copy chat-inline-media-card__action chat-inline-media-card__action--icon';
    button.dataset.action = CHAT_ACTIONS.COPY_INLINE_MEDIA_REFERENCE;
    button.dataset['inlineMediaCopyValue'] = value;
    setLabeledActionAttributes(button, label);
    appendActionIcon(doc, button, 'copy');
    return button;
};

const createOpenFilesFolderSettingsButton = (doc: Document): HTMLButtonElement => {
    const button = doc.createElement('button');
    button.type = 'button';
    const label = i18n.t('chat.inlinePreviews.openFolderSettings');
    button.className = 'ui-icon-button ui-icon-button-small ui-variant-neutral chat-inline-media-card__action chat-inline-media-card__action--icon chat-inline-media-card__open-folder-settings';
    button.dataset.action = CHAT_ACTIONS.OPEN_FILES_FOLDER_SETTINGS;
    setLabeledActionAttributes(button, label);
    appendActionIcon(doc, button, 'settings');
    return button;
};

export { appendInlineMediaDownloadAction, appendInlineMediaSourceActions, createCopyButton, createLinkAction, createOpenButton, createOpenFilesFolderSettingsButton, createOpenSourceAction };
