/* SoAI - Non-preview reference rendering for canonical preview tokens when inline previews are disabled [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaDisabledReferences.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parentVirtualPath, toVirtualPath } from '@core/fileexplorerbrowser/paths.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { createCopyButton, createOpenSourceAction } from '@features/chat/message/enhancers/inlineMultimediaCardActions.ts';
import { buildCardRoot } from '@features/chat/message/enhancers/inlineMultimediaCardLayout.ts';
import { type PreviewReferenceToken, type PreviewReferenceType } from '@features/chat/message/enhancers/inlineMultimediaPreviewContract.ts';
import { resolveInlineMultimediaReferenceTitle } from '@features/chat/message/enhancers/inlineMultimediaReferenceTitle.ts';
import { buildFileExplorerDeepLink } from '@features/chat/message/enhancers/inlineMultimediaUrls.ts';

interface InlineMediaDisabledReferenceDescriptor {
    type: PreviewReferenceType | null;
    target: string;
    label: string | null;
}

const resolveDisabledReferenceTitle = (descriptor: InlineMediaDisabledReferenceDescriptor): string => {
    return resolveInlineMultimediaReferenceTitle(descriptor) ?? i18n.t('chat.inlinePreviews.referenceTitle');
};

const resolveDisabledReferenceSubtitle = (descriptor: InlineMediaDisabledReferenceDescriptor): string => {
    if (descriptor.type === 'absolute_path') {
        return i18n.t('chat.inlinePreviews.absolutePathReferenceSubtitle');
    }
    if (descriptor.type === 'virtual_path') {
        return i18n.t('chat.inlinePreviews.virtualPathReferenceSubtitle');
    }
    if (descriptor.type === 'remote_url') {
        return i18n.t('chat.inlinePreviews.remoteUrlReferenceSubtitle');
    }
    return i18n.t('chat.inlinePreviews.referenceSubtitle');
};

const appendReferenceValue = (doc: Document, shell: ReturnType<typeof buildCardRoot>, value: string): void => {
    const text = toTrimmedString(value);
    if (!text) {
        return;
    }
    const referenceValue = doc.createElement('div');
    referenceValue.className = 'chat-inline-media-card__reference-value';
    referenceValue.textContent = text;
    shell.body.appendChild(referenceValue);
};

const createDisabledReferenceCard = (doc: Document, descriptor: InlineMediaDisabledReferenceDescriptor): HTMLElement => {
    const shell = buildCardRoot(doc, { type: 'disabled' });
    shell.root.dataset['inlineMediaStatus'] = 'disabled';
    if (descriptor.type) {
        shell.root.dataset['inlineMediaTokenType'] = descriptor.type;
    }
    shell.title.textContent = resolveDisabledReferenceTitle(descriptor);
    shell.subtitle.textContent = resolveDisabledReferenceSubtitle(descriptor);
    appendReferenceValue(doc, shell, descriptor.target);

    if (descriptor.type === 'remote_url') {
        shell.actions.appendChild(createOpenSourceAction(doc, descriptor.target));
        shell.actions.appendChild(createCopyButton(doc, descriptor.target));
        return shell.root;
    }

    if (descriptor.type === 'virtual_path') {
        const virtualPath = toVirtualPath(descriptor.target);
        shell.actions.appendChild(
            createOpenSourceAction(
                doc,
                buildFileExplorerDeepLink({
                    directoryPath: parentVirtualPath(virtualPath),
                    highlightPath: virtualPath,
                    search: null
                })
            )
        );
        shell.actions.appendChild(createCopyButton(doc, virtualPath));
        return shell.root;
    }

    if (descriptor.type === 'absolute_path') {
        shell.actions.appendChild(createCopyButton(doc, descriptor.target));
        return shell.root;
    }

    return shell.root;
};

const renderDisabledReferenceToken = (doc: Document, token: PreviewReferenceToken): HTMLElement => {
    return createDisabledReferenceCard(doc, {
        type: token.type,
        target: token.target,
        label: token.label
    });
};

export { renderDisabledReferenceToken };
