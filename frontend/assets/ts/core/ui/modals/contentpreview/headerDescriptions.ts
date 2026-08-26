/* SoAI - Content preview header description text [frontend/assets/ts/core/ui/modals/contentpreview/headerDescriptions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveFileEntryTypeLabel } from '@core/fileexplorerbrowser/entryTypeLabels.ts';
import { classifyFileBrowserMimeType, normalizeFileBrowserMimeType } from '@core/fileexplorerbrowser/mediaClassification.ts';
import type { FileBrowserMetadata } from '@core/fileexplorerbrowser/types.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ContentPreviewType } from '@core/ui/modals/contentpreview/types.ts';

type ChatPreviewHeaderDescriptionType = Extract<ContentPreviewType, 'audio' | 'document' | 'embed' | 'file' | 'image' | 'text' | 'video'>;

const resolveFileExplorerPreviewHeaderDescriptionForFile = (mimeType: string): string => {
    const mediaType = classifyFileBrowserMimeType(mimeType);
    const typeId = mediaType === 'file' ? 'binary' : mediaType;
    return combineLabelAndMimeType(resolveFileEntryTypeLabel(typeId), mimeType);
};

const combineLabelAndMimeType = (label: string, mimeType: string | null): string => {
    const normalizedMimeType = mimeType ? normalizeFileBrowserMimeType(mimeType) : '';
    if (!normalizedMimeType) {
        return label;
    }
    return `${label} - ${normalizedMimeType}`;
};

const resolveFileExplorerPreviewHeaderDescription = (metadata: FileBrowserMetadata): string => {
    return combineLabelAndMimeType(resolveFileEntryTypeLabel(metadata.typeId), metadata.mimeType);
};

const resolveChatPreviewTypeLabel = (type: ChatPreviewHeaderDescriptionType): string => {
    switch (type) {
        case 'audio':
            return i18n.t('contentPreview.headerDescriptions.chatAudio');
        case 'document':
            return i18n.t('contentPreview.headerDescriptions.chatDocument');
        case 'embed':
            return i18n.t('contentPreview.headerDescriptions.chatEmbed');
        case 'file':
            return i18n.t('contentPreview.headerDescriptions.chatFile');
        case 'image':
            return i18n.t('contentPreview.headerDescriptions.chatImage');
        case 'text':
            return i18n.t('contentPreview.headerDescriptions.chatText');
        case 'video':
            return i18n.t('contentPreview.headerDescriptions.chatVideo');
    }
};

const resolveChatPreviewHeaderDescription = (type: ChatPreviewHeaderDescriptionType, contentType: string | null): string => combineLabelAndMimeType(resolveChatPreviewTypeLabel(type), contentType);

export { resolveChatPreviewHeaderDescription, resolveFileExplorerPreviewHeaderDescription, resolveFileExplorerPreviewHeaderDescriptionForFile };
export type { ChatPreviewHeaderDescriptionType };
