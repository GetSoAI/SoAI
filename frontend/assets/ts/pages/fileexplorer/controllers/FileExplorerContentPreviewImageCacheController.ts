/* SoAI - File Explorer adjacent image preparation and ownership [frontend/assets/ts/pages/fileexplorer/controllers/FileExplorerContentPreviewImageCacheController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { raceWithAbortSignal, runWithAbortSignalScope, throwIfAborted } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isFileBrowserImagePreviewMimeType } from '@core/fileexplorerbrowser/mediaClassification.ts';
import type { FileBrowserMetadata } from '@core/fileexplorerbrowser/types.ts';
import { uniqueStringsPreserveOrder } from '@core/normalize.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { withAbortableTimeout } from '@core/primitives/withAbortableTimeout.ts';
import { loadContentPreviewImage } from '@core/ui/modals/contentpreview/imageViewerScene.ts';
import { createFileExplorerContentPreviewMedia, revokeFileExplorerContentPreviewMediaUrl, type FileExplorerContentPreviewMedia, type FileExplorerContentPreviewMediaHost } from '@pages/fileexplorer/controllers/FileExplorerContentPreviewMediaController.ts';

type PreparedImageResult = Readonly<{ type: 'ready'; media: FileExplorerContentPreviewMedia; metadata: FileBrowserMetadata }> | Readonly<{ type: 'unavailable'; error: Error }> | Readonly<{ type: 'cancelled' }>;
type PreparedImage = Readonly<{ controller: AbortController; promise: Promise<PreparedImageResult> }>;
type ImagePreparationHost = FileExplorerContentPreviewMediaHost & Readonly<{ loadMetadata: (path: string, signal?: AbortSignal) => Promise<FileBrowserMetadata> }>;

class FileExplorerContentPreviewImageCacheController {
    readonly #host: ImagePreparationHost;
    readonly #entries = new Map<string, PreparedImage>();

    constructor(host: ImagePreparationHost) {
        this.#host = host;
    }

    warm(paths: readonly string[]): void {
        const adjacent = uniqueStringsPreserveOrder(paths).slice(0, 2);
        for (const [path, entry] of this.#entries) {
            if (!adjacent.includes(path)) {
                this.#release(entry);
                this.#entries.delete(path);
            }
        }
        for (const path of adjacent) {
            if (!this.#entries.has(path)) {
                const controller = new AbortController();
                this.#entries.set(path, { controller, promise: this.#prepare(path, controller.signal) });
            }
        }
    }

    async take(metadata: FileBrowserMetadata, signal: AbortSignal): Promise<FileExplorerContentPreviewMedia> {
        return await withAbortableTimeout(
            (timeoutSignal) =>
                runWithAbortSignalScope([signal, timeoutSignal], async (loadSignal) => {
                    throwIfAborted(loadSignal);
                    const entry = this.#entries.get(metadata.path);
                    if (!entry) {
                        return await createFileExplorerContentPreviewMedia(this.#host, metadata.path, loadSignal);
                    }
                    this.#entries.delete(metadata.path);
                    let transferred = false;
                    try {
                        const result = await raceWithAbortSignal(entry.promise, loadSignal);
                        const preparedImageIsCurrent = result.type === 'ready' && result.metadata.size === metadata.size && result.metadata.modifiedAt === metadata.modifiedAt && result.metadata.sha256 === metadata.sha256 && result.metadata.mimeType === metadata.mimeType;
                        if (result.type === 'ready' && preparedImageIsCurrent) {
                            throwIfAborted(loadSignal);
                            transferred = true;
                            return result.media;
                        }
                        return await createFileExplorerContentPreviewMedia(this.#host, metadata.path, loadSignal);
                    } finally {
                        if (!transferred) {
                            this.#release(entry);
                        }
                    }
                }),
            { timeoutMs: 30000, timeoutMessage: 'Image preview preparation exceeded its deadline' }
        );
    }

    clear(): void {
        for (const entry of this.#entries.values()) {
            this.#release(entry);
        }
        this.#entries.clear();
    }

    async #prepare(path: string, signal: AbortSignal): Promise<PreparedImageResult> {
        try {
            return await withAbortableTimeout(
                (timeoutSignal) =>
                    runWithAbortSignalScope([signal, timeoutSignal], async (loadSignal): Promise<PreparedImageResult> => {
                        const metadata = await raceWithAbortSignal(this.#host.loadMetadata(path, loadSignal), loadSignal);
                        throwIfAborted(loadSignal);
                        if (metadata.isDirectory || !isFileBrowserImagePreviewMimeType(metadata.mimeType)) {
                            return { type: 'unavailable', error: new Error('Adjacent image is no longer an image file') };
                        }
                        const media = await createFileExplorerContentPreviewMedia(this.#host, path, loadSignal);
                        let prepared = false;
                        try {
                            await loadContentPreviewImage(media.sourceUrl, metadata.name, dom.getDocument(), loadSignal);
                            throwIfAborted(loadSignal);
                            prepared = true;
                            return { type: 'ready', media, metadata };
                        } finally {
                            if (!prepared) {
                                revokeFileExplorerContentPreviewMediaUrl(media.sourceUrl);
                            }
                        }
                    }),
                { timeoutMs: 30000, timeoutMessage: 'Adjacent image preparation exceeded its deadline' }
            );
        } catch (error) {
            const runtimeError = ensureError(error);
            return signal.aborted ? { type: 'cancelled' } : { type: 'unavailable', error: runtimeError };
        }
    }

    #release(entry: PreparedImage): void {
        entry.controller.abort();
        terminateHandledPromise(
            entry.promise.then((result) => {
                if (result.type === 'ready') {
                    revokeFileExplorerContentPreviewMediaUrl(result.media.sourceUrl);
                }
            })
        );
    }
}

export { FileExplorerContentPreviewImageCacheController };
