/* SoAI - Chat feature inline multimedia resolved card factory [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaResolvedCardFactory.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { ContentPreviewSourceReference } from '@core/ui/modals/contentpreview/types.ts';
import { createAudioCard, createImageCard, createVideoCard } from '@features/chat/message/enhancers/inlineMultimediaCardsMedia.ts';
import { createDocumentCard, createFileCard, createFolderCard, type InlineMediaFolderPreview } from '@features/chat/message/enhancers/inlineMultimediaCardsFiles.ts';
import { createTextCard } from '@features/chat/message/enhancers/inlineMultimediaCardsText.ts';
import { createErrorCard } from '@features/chat/message/enhancers/inlineMultimediaCardsStatus.ts';
import { isInlineMediaMetadataPreviewType, type InlineMediaMetadataPreviewType, type InlineMediaOpenAction, type ResolvedInlineMediaPreviewType } from '@features/chat/message/enhancers/inlineMultimediaCardTypes.ts';
import { createInlineMediaAudioOpenAction, createInlineMediaImageOpenAction, createInlineMediaTextOpenAction, createInlineMediaVideoOpenAction } from '@features/chat/message/enhancers/inlineMultimediaOpenAction.ts';

type ResolvedInlineMediaPreviewArguments = {
    doc: Document;
    type: ResolvedInlineMediaPreviewType;
    title: string;
    target: string;
    sourcePath: string;
    rawToken: string;
    openFileExplorerHref: string;
    downloadHref: string | null;
    downloadName: string | null;
    previewUrl: string | null;
    mimeType: string | null;
    size: number | null;
    textPreviewContent: string | null;
    folderPreview: InlineMediaFolderPreview | null;
};

type ResolvedInlineMediaPreviewDescriptor = Omit<ResolvedInlineMediaPreviewArguments, 'doc'>;

type ResolvedInlineMediaMetadata = {
    previewUrl: string;
    contentType: string;
    size: number;
};

const normalizeTextPreviewContent = (content: string): string => {
    return content.replaceAll('\r\n', '\n').replaceAll('\r', '\n');
};

const resolveMetadataContractFailureCard = (inputArguments: ResolvedInlineMediaPreviewArguments): HTMLElement => {
    return createErrorCard(inputArguments.doc, inputArguments.title, i18n.t('chat.inlinePreviews.unavailableMessage'), {
        openFileExplorerHref: inputArguments.openFileExplorerHref,
        searchHref: null,
        copyValue: inputArguments.rawToken
    });
};

const readResolvedInlineMediaMetadata = (inputArguments: ResolvedInlineMediaPreviewArguments): ResolvedInlineMediaMetadata | null => {
    if (inputArguments.previewUrl === null || inputArguments.mimeType === null || inputArguments.size === null) {
        return null;
    }
    if (!Number.isFinite(inputArguments.size) || !Number.isInteger(inputArguments.size) || inputArguments.size < 0) {
        return null;
    }
    return {
        previewUrl: inputArguments.previewUrl,
        contentType: inputArguments.mimeType,
        size: inputArguments.size
    };
};

const createResolvedMediaOpenAction = (inputArguments: ResolvedInlineMediaPreviewArguments, type: InlineMediaMetadataPreviewType, metadata: ResolvedInlineMediaMetadata): InlineMediaOpenAction => {
    const sourceReference: ContentPreviewSourceReference = { type: 'path', value: inputArguments.sourcePath };
    const shared = {
        previewUrl: metadata.previewUrl,
        openSourceUrl: inputArguments.openFileExplorerHref,
        title: inputArguments.title,
        downloadName: inputArguments.downloadName,
        downloadUrl: inputArguments.downloadHref,
        contentType: metadata.contentType,
        contentLength: metadata.size,
        sourceReference,
        requireMetadata: true
    };
    if (type === 'image') {
        return createInlineMediaImageOpenAction(shared);
    }
    if (type === 'audio') {
        return createInlineMediaAudioOpenAction(shared);
    }
    return createInlineMediaVideoOpenAction(shared);
};

const createResolvedMediaCard = (inputArguments: ResolvedInlineMediaPreviewArguments, type: InlineMediaMetadataPreviewType, metadata: ResolvedInlineMediaMetadata): HTMLElement => {
    const action = createResolvedMediaOpenAction(inputArguments, type, metadata);
    const common = {
        title: inputArguments.title,
        referenceText: inputArguments.target,
        referenceHref: inputArguments.openFileExplorerHref,
        referenceLinkType: 'chat-path',
        openAction: action,
        downloadHref: inputArguments.downloadHref
    };
    if (type === 'image') {
        return createImageCard(inputArguments.doc, {
            ...common,
            thumbnailUrl: metadata.previewUrl
        });
    }
    if (type === 'audio') {
        return createAudioCard(inputArguments.doc, {
            ...common,
            audioUrl: metadata.previewUrl
        });
    }
    return createVideoCard(inputArguments.doc, {
        ...common,
        videoUrl: metadata.previewUrl
    });
};

const createResolvedInlineMediaReplacementCard = (inputArguments: ResolvedInlineMediaPreviewArguments): HTMLElement => {
    const type = inputArguments.type;
    const title = inputArguments.title;
    const openExplorerHref = inputArguments.openFileExplorerHref;
    const downloadHref = inputArguments.downloadHref;
    const referenceText = inputArguments.target;

    if (type === 'text') {
        const content = inputArguments.textPreviewContent;
        if (content === null) {
            return resolveMetadataContractFailureCard(inputArguments);
        }
        const modalContent = normalizeTextPreviewContent(content);
        const action: InlineMediaOpenAction = createInlineMediaTextOpenAction({
            textContent: modalContent,
            openSourceUrl: openExplorerHref,
            title,
            contentType: inputArguments.mimeType,
            contentLength: inputArguments.size,
            sourceReference: { type: 'path', value: inputArguments.sourcePath }
        });
        return createTextCard(inputArguments.doc, {
            title,
            referenceText,
            referenceHref: openExplorerHref,
            referenceLinkType: 'chat-path',
            excerpt: modalContent,
            openAction: action,
            sourceHref: openExplorerHref
        });
    }

    if (isInlineMediaMetadataPreviewType(type)) {
        const metadata = readResolvedInlineMediaMetadata(inputArguments);
        if (metadata === null) {
            return resolveMetadataContractFailureCard(inputArguments);
        }
        return createResolvedMediaCard(inputArguments, type, metadata);
    }

    if (type === 'document') {
        return createDocumentCard(inputArguments.doc, {
            title,
            referenceText,
            referenceHref: openExplorerHref,
            referenceLinkType: 'chat-path',
            openFileExplorerHref: openExplorerHref,
            downloadHref
        });
    }

    if (type === 'folder') {
        if (inputArguments.folderPreview === null) {
            return resolveMetadataContractFailureCard(inputArguments);
        }
        return createFolderCard(inputArguments.doc, {
            title,
            referenceText,
            referenceHref: openExplorerHref,
            referenceLinkType: 'chat-path',
            openFileExplorerHref: openExplorerHref,
            preview: inputArguments.folderPreview
        });
    }

    return createFileCard(inputArguments.doc, {
        title,
        referenceText,
        referenceHref: openExplorerHref,
        referenceLinkType: 'chat-path',
        openFileExplorerHref: openExplorerHref,
        downloadHref
    });
};

export { createResolvedInlineMediaReplacementCard };
export type { ResolvedInlineMediaPreviewArguments, ResolvedInlineMediaPreviewDescriptor };
