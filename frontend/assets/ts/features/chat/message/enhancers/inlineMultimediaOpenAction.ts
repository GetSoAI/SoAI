/* SoAI - Canonical InlineMediaOpenAction builders for preview cards [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaOpenAction.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ContentPreviewSourceReference } from '@core/ui/modals/contentpreview/types.ts';
import type { InlineMediaOpenAction } from '@features/chat/message/enhancers/inlineMultimediaCardTypes.ts';

type OpenActionArgumentsBase = {
    previewUrl: string;
    openSourceUrl: string;
    title: string;
    downloadName: string | null;
    downloadUrl: string | null;
    contentType: string | null;
    contentLength: number | null;
    sourceReference: ContentPreviewSourceReference | null;
    requireMetadata: boolean;
};

const createInlineMediaOpenAction = (type: 'image' | 'audio' | 'video', inputArguments: OpenActionArgumentsBase): InlineMediaOpenAction => {
    return {
        type,
        previewUrl: inputArguments.previewUrl,
        openSourceUrl: inputArguments.openSourceUrl,
        title: inputArguments.title,
        downloadName: inputArguments.downloadName,
        downloadUrl: inputArguments.downloadUrl,
        contentType: inputArguments.contentType,
        contentLength: inputArguments.contentLength,
        sourceReference: inputArguments.sourceReference,
        requireMetadata: inputArguments.requireMetadata
    };
};

const createInlineMediaEmbedOpenAction = (inputArguments: Pick<OpenActionArgumentsBase, 'previewUrl' | 'openSourceUrl' | 'title'>): InlineMediaOpenAction => {
    return {
        type: 'embed',
        previewUrl: inputArguments.previewUrl,
        openSourceUrl: inputArguments.openSourceUrl,
        title: inputArguments.title,
        downloadName: null,
        downloadUrl: null,
        contentType: null,
        contentLength: null,
        sourceReference: { type: 'url', value: inputArguments.openSourceUrl },
        requireMetadata: false
    };
};

const createInlineMediaImageOpenAction = (inputArguments: OpenActionArgumentsBase): InlineMediaOpenAction => {
    return createInlineMediaOpenAction('image', inputArguments);
};

const createInlineMediaAudioOpenAction = (inputArguments: OpenActionArgumentsBase): InlineMediaOpenAction => {
    return createInlineMediaOpenAction('audio', inputArguments);
};

const createInlineMediaVideoOpenAction = (inputArguments: OpenActionArgumentsBase): InlineMediaOpenAction => {
    return createInlineMediaOpenAction('video', inputArguments);
};

const createInlineMediaTextOpenAction = (inputArguments: { textContent: string; openSourceUrl: string; title: string; contentType: string | null; contentLength: number | null; sourceReference: ContentPreviewSourceReference | null }): InlineMediaOpenAction => {
    return {
        type: 'text',
        textContent: inputArguments.textContent,
        openSourceUrl: inputArguments.openSourceUrl,
        title: inputArguments.title,
        contentType: inputArguments.contentType,
        contentLength: inputArguments.contentLength,
        sourceReference: inputArguments.sourceReference
    };
};

export { createInlineMediaAudioOpenAction, createInlineMediaEmbedOpenAction, createInlineMediaImageOpenAction, createInlineMediaTextOpenAction, createInlineMediaVideoOpenAction };
