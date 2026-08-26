/* SoAI - Chat feature inline multimedia remote link direct cards [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaRemoteLinkDirectCards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createAudioCard, createEmbedCard, createImageCard, createVideoCard } from '@features/chat/message/enhancers/inlineMultimediaCardsMedia.ts';
import { createDocumentCard, createFileCard } from '@features/chat/message/enhancers/inlineMultimediaCardsFiles.ts';
import type { InlineMediaOpenAction } from '@features/chat/message/enhancers/inlineMultimediaCardTypes.ts';
import { createInlineMediaAudioOpenAction, createInlineMediaEmbedOpenAction, createInlineMediaImageOpenAction, createInlineMediaVideoOpenAction } from '@features/chat/message/enhancers/inlineMultimediaOpenAction.ts';
import type { RemoteLinkPreview } from '@features/chat/message/enhancers/inlineMultimediaRemoteLinkPayloads.ts';

interface RemoteLinkDirectCardOptions {
    doc: Document;
    preview: RemoteLinkPreview;
    referenceUrl: string;
    title: string;
}

const createRemoteMediaOpenAction = (preview: RemoteLinkPreview, title: string): InlineMediaOpenAction | null => {
    if (preview.type === 'image') {
        return createInlineMediaImageOpenAction({
            previewUrl: preview.previewUrl,
            openSourceUrl: preview.sourceUrl,
            title,
            downloadName: null,
            downloadUrl: preview.downloadUrl,
            contentType: null,
            contentLength: null,
            sourceReference: { type: 'url', value: preview.sourceUrl },
            requireMetadata: false
        });
    }
    if (preview.type === 'audio') {
        return createInlineMediaAudioOpenAction({
            previewUrl: preview.previewUrl,
            openSourceUrl: preview.sourceUrl,
            title,
            downloadName: null,
            downloadUrl: preview.downloadUrl,
            contentType: null,
            contentLength: null,
            sourceReference: { type: 'url', value: preview.sourceUrl },
            requireMetadata: false
        });
    }
    if (preview.type === 'video') {
        return createInlineMediaVideoOpenAction({
            previewUrl: preview.previewUrl,
            openSourceUrl: preview.sourceUrl,
            title,
            downloadName: null,
            downloadUrl: preview.downloadUrl,
            contentType: null,
            contentLength: null,
            sourceReference: { type: 'url', value: preview.sourceUrl },
            requireMetadata: false
        });
    }
    return null;
};

const createRemoteLinkDirectPreviewCard = (options: RemoteLinkDirectCardOptions): HTMLElement | null => {
    const preview = options.preview;
    if (preview.type === 'embed') {
        const action: InlineMediaOpenAction = createInlineMediaEmbedOpenAction({
            previewUrl: preview.embedUrl,
            openSourceUrl: preview.sourceUrl,
            title: options.title
        });
        return createEmbedCard(options.doc, {
            title: options.title,
            thumbnailUrl: preview.thumbnailUrl,
            referenceText: options.referenceUrl,
            referenceHref: options.referenceUrl,
            referenceLinkType: null,
            openAction: action,
            sourceHref: preview.sourceUrl
        });
    }
    if (preview.type === 'image') {
        const action = createRemoteMediaOpenAction(preview, options.title);
        if (action === null) {
            return null;
        }
        return createImageCard(options.doc, {
            title: options.title,
            thumbnailUrl: preview.previewUrl,
            referenceText: options.referenceUrl,
            referenceHref: options.referenceUrl,
            referenceLinkType: null,
            openAction: action,
            downloadHref: preview.downloadUrl
        });
    }
    if (preview.type === 'audio') {
        const action = createRemoteMediaOpenAction(preview, options.title);
        if (action === null) {
            return null;
        }
        return createAudioCard(options.doc, {
            title: options.title,
            audioUrl: preview.previewUrl,
            referenceText: options.referenceUrl,
            referenceHref: options.referenceUrl,
            referenceLinkType: null,
            openAction: action,
            downloadHref: preview.downloadUrl
        });
    }
    if (preview.type === 'video') {
        const action = createRemoteMediaOpenAction(preview, options.title);
        if (action === null) {
            return null;
        }
        return createVideoCard(options.doc, {
            title: options.title,
            videoUrl: preview.previewUrl,
            referenceText: options.referenceUrl,
            referenceHref: options.referenceUrl,
            referenceLinkType: null,
            openAction: action,
            downloadHref: preview.downloadUrl
        });
    }
    if (preview.type === 'document') {
        return createDocumentCard(options.doc, {
            title: options.title,
            referenceText: options.referenceUrl,
            referenceHref: options.referenceUrl,
            referenceLinkType: null,
            openFileExplorerHref: null,
            downloadHref: preview.downloadUrl
        });
    }
    if (preview.type === 'file') {
        return createFileCard(options.doc, {
            title: options.title,
            referenceText: options.referenceUrl,
            referenceHref: options.referenceUrl,
            referenceLinkType: null,
            openFileExplorerHref: null,
            downloadHref: preview.downloadUrl
        });
    }
    return null;
};

export { createRemoteLinkDirectPreviewCard };
