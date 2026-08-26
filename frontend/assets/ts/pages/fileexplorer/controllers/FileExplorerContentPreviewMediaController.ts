/* SoAI - File explorer page control layer content preview media controller [frontend/assets/ts/pages/fileexplorer/controllers/FileExplorerContentPreviewMediaController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ContentPreviewImageMetadata } from '@core/ui/modals/contentpreview/types.ts';
import type { BufferedApiResponse } from '@core/api/bufferedResponse.ts';

type FileExplorerContentPreviewMediaHost = Readonly<{
    downloadResponse: (path: string) => Promise<BufferedApiResponse>;
}>;

type FileExplorerContentPreviewMediaType = 'audio' | 'image' | 'video';

type FileExplorerContentPreviewMedia = Readonly<{
    sourceUrl: string;
    imageMetadata: ContentPreviewImageMetadata | null;
}>;

const createFileExplorerContentPreviewMedia = async (host: FileExplorerContentPreviewMediaHost, path: string): Promise<FileExplorerContentPreviewMedia> => {
    const response = await host.downloadResponse(path);
    const contentTypeHeader = response.headers.get('Content-Type');
    const contentLengthHeader = response.headers.get('Content-Length');
    const blob = response.body;
    const contentType = contentTypeHeader && contentTypeHeader.trim() ? contentTypeHeader.trim() : blob.type.trim() ? blob.type.trim() : null;
    const contentLengthValue = contentLengthHeader ? Number(contentLengthHeader) : blob.size;
    const contentLength = Number.isFinite(contentLengthValue) && contentLengthValue >= 0 ? contentLengthValue : blob.size;
    return Object.freeze({
        sourceUrl: URL.createObjectURL(blob),
        imageMetadata: Object.freeze({
            contentType,
            contentLength
        })
    });
};

const revokeFileExplorerContentPreviewMediaUrl = (url: string | null): void => {
    if (!url) {
        return;
    }
    URL.revokeObjectURL(url);
};

const FileExplorerContentPreviewMediaController = Object.freeze({
    createFileExplorerContentPreviewMedia,
    revokeFileExplorerContentPreviewMediaUrl
});

export { FileExplorerContentPreviewMediaController };
export { createFileExplorerContentPreviewMedia, revokeFileExplorerContentPreviewMediaUrl };
export type { FileExplorerContentPreviewMedia, FileExplorerContentPreviewMediaHost, FileExplorerContentPreviewMediaType };
