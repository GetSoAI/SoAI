/* SoAI - Chat feature inline multimedia cards status [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaCardsStatus.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { InlineMediaErrorActions } from '@features/chat/message/enhancers/inlineMultimediaCardTypes.ts';
import { appendInlineMediaDownloadAction, createCopyButton, createLinkAction, createOpenFilesFolderSettingsButton, createOpenSourceAction } from '@features/chat/message/enhancers/inlineMultimediaCardActions.ts';
import { buildCardRoot } from '@features/chat/message/enhancers/inlineMultimediaCardLayout.ts';

const createPendingCard = (doc: Document, titleText: string): HTMLElement => {
    const shell = buildCardRoot(doc, { type: 'pending' });
    shell.title.textContent = titleText;
    shell.subtitle.textContent = i18n.t('common.loading');
    const spinner = doc.createElement('span');
    spinner.className = 'loading-spinner';
    spinner.setAttribute('aria-hidden', 'true');
    shell.body.appendChild(spinner);
    return shell.root;
};

const createErrorCard = (doc: Document, titleText: string, messageText: string, actions: InlineMediaErrorActions): HTMLElement => {
    const shell = buildCardRoot(doc, {
        type: 'unavailable',
        isError: true
    });
    shell.title.textContent = titleText;
    shell.subtitle.textContent = i18n.t('chat.inlinePreviews.unavailableSubtitle');
    const message = doc.createElement('div');
    message.className = 'chat-inline-media-card__error-message';
    message.textContent = messageText;
    shell.body.appendChild(message);

    const openSourceHref = actions.openFileExplorerHref ? actions.openFileExplorerHref : actions.openSourceHref ? actions.openSourceHref : null;
    if (openSourceHref) {
        shell.actions.appendChild(createOpenSourceAction(doc, openSourceHref));
    }
    if (actions.searchHref) {
        shell.actions.appendChild(
            createLinkAction(doc, {
                href: actions.searchHref,
                label: i18n.t('chat.inlinePreviews.searchInFileExplorer'),
                iconName: 'search'
            })
        );
    }
    appendInlineMediaDownloadAction(doc, shell.actions, actions.downloadHref ?? null);
    if (actions.openFilesFolderSettings === true) {
        shell.actions.appendChild(createOpenFilesFolderSettingsButton(doc));
    }
    if (actions.copyValue) {
        shell.actions.appendChild(createCopyButton(doc, actions.copyValue));
    }
    return shell.root;
};

export { createErrorCard, createPendingCard };
