/* SoAI - Chat feature inline multimedia card types [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaCardTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ContentPreviewSourceReference } from '@core/ui/modals/contentpreview/types.ts';

type InlineMediaType = 'image' | 'audio' | 'video' | 'embed' | 'text' | 'document' | 'file' | 'folder';

type InlineMediaPreviewType = InlineMediaType | 'link';
type InlineMediaCardType = InlineMediaPreviewType | 'pending' | 'unavailable' | 'disabled';
type ResolvedInlineMediaPreviewType = 'image' | 'audio' | 'video' | 'text' | 'document' | 'file' | 'folder';
type RemoteInlineMediaPreviewType = 'image' | 'audio' | 'video' | 'embed' | 'text' | 'document' | 'file' | 'link';
type InlineMediaMetadataPreviewType = 'image' | 'audio' | 'video';
type InlineMediaDownloadOnlyType = 'document' | 'file';

const INLINE_MEDIA_PREVIEW_TYPES: readonly InlineMediaPreviewType[] = ['image', 'audio', 'video', 'embed', 'text', 'document', 'file', 'folder', 'link'];
const RESOLVED_INLINE_MEDIA_PREVIEW_TYPES: readonly ResolvedInlineMediaPreviewType[] = ['image', 'audio', 'video', 'text', 'document', 'file', 'folder'];
const REMOTE_INLINE_MEDIA_PREVIEW_TYPES: readonly RemoteInlineMediaPreviewType[] = ['image', 'audio', 'video', 'embed', 'text', 'document', 'file', 'link'];
const INLINE_MEDIA_OPEN_ACTION_TYPES: readonly InlineMediaOpenAction['type'][] = ['image', 'audio', 'video', 'embed', 'text'];
const INLINE_MEDIA_METADATA_PREVIEW_TYPES: readonly InlineMediaMetadataPreviewType[] = ['image', 'audio', 'video'];
const INLINE_MEDIA_DOWNLOAD_ONLY_TYPES: readonly InlineMediaDownloadOnlyType[] = ['document', 'file'];

type InlineMediaOpenAction =
    | {
          type: 'image' | 'audio' | 'video' | 'embed';
          previewUrl: string;
          openSourceUrl: string;
          title: string;
          downloadName: string | null;
          downloadUrl: string | null;
          contentType: string | null;
          contentLength: number | null;
          sourceReference: ContentPreviewSourceReference | null;
          requireMetadata: boolean;
      }
    | {
          type: 'text';
          textContent: string;
          openSourceUrl: string;
          title: string;
          contentType: string | null;
          contentLength: number | null;
          sourceReference: ContentPreviewSourceReference | null;
      };

interface InlineMediaErrorActions {
    openFileExplorerHref: string | null;
    searchHref: string | null;
    copyValue: string | null;
    openSourceHref?: string | null;
    downloadHref?: string | null;
    openFilesFolderSettings?: boolean;
}

const isInlineMediaOpenActionType = (value: string): value is InlineMediaOpenAction['type'] => {
    return INLINE_MEDIA_OPEN_ACTION_TYPES.some((allowedValue) => allowedValue === value);
};

const isInlineMediaPreviewType = (value: string): value is InlineMediaPreviewType => {
    return INLINE_MEDIA_PREVIEW_TYPES.some((allowedValue) => allowedValue === value);
};

const isResolvedInlineMediaPreviewType = (value: string): value is ResolvedInlineMediaPreviewType => {
    return RESOLVED_INLINE_MEDIA_PREVIEW_TYPES.some((allowedValue) => allowedValue === value);
};

const isInlineMediaMetadataPreviewType = (value: string): value is InlineMediaMetadataPreviewType => {
    return INLINE_MEDIA_METADATA_PREVIEW_TYPES.some((allowedValue) => allowedValue === value);
};

const isInlineMediaDownloadOnlyType = (value: string): value is InlineMediaDownloadOnlyType => {
    return INLINE_MEDIA_DOWNLOAD_ONLY_TYPES.some((allowedValue) => allowedValue === value);
};

export { INLINE_MEDIA_DOWNLOAD_ONLY_TYPES, INLINE_MEDIA_METADATA_PREVIEW_TYPES, INLINE_MEDIA_OPEN_ACTION_TYPES, INLINE_MEDIA_PREVIEW_TYPES, REMOTE_INLINE_MEDIA_PREVIEW_TYPES, RESOLVED_INLINE_MEDIA_PREVIEW_TYPES, isInlineMediaDownloadOnlyType, isInlineMediaMetadataPreviewType, isInlineMediaOpenActionType, isInlineMediaPreviewType, isResolvedInlineMediaPreviewType };
export type { InlineMediaCardType, InlineMediaDownloadOnlyType, InlineMediaErrorActions, InlineMediaMetadataPreviewType, InlineMediaType, InlineMediaOpenAction, InlineMediaPreviewType, RemoteInlineMediaPreviewType, ResolvedInlineMediaPreviewType };
