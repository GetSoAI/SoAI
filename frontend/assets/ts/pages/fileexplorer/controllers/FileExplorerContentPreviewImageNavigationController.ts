/* SoAI - File Explorer content preview image navigation controller [frontend/assets/ts/pages/fileexplorer/controllers/FileExplorerContentPreviewImageNavigationController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { trimStringList, uniqueStringsPreserveOrder } from '@core/normalize.ts';
import type { ContentPreviewImageNavigation, ContentPreviewImageNavigationDirection } from '@core/ui/modals/contentpreview/types.ts';

type FileExplorerContentPreviewImageNavigationHost = Readonly<{
    getCurrentFolderImagePaths: () => readonly string[];
    getCurrentPath: () => string | null;
    openPath: (path: string, direction: ContentPreviewImageNavigationDirection) => Promise<void>;
}>;

class FileExplorerContentPreviewImageNavigationController {
    readonly #host: FileExplorerContentPreviewImageNavigationHost;

    constructor(host: FileExplorerContentPreviewImageNavigationHost) {
        this.#host = host;
    }

    createNavigation(): ContentPreviewImageNavigation | null {
        const paths = this.#getCurrentFolderImagePaths();
        if (paths.length <= 1) {
            return null;
        }
        const currentPath = this.#host.getCurrentPath();
        if (!currentPath || !paths.includes(currentPath)) {
            return null;
        }
        const currentIndex = paths.indexOf(currentPath);
        const previousPath = paths[(currentIndex - 1 + paths.length) % paths.length];
        const nextPath = paths[(currentIndex + 1) % paths.length];
        if (!previousPath || !nextPath) {
            throw new Error('File Explorer image navigation could not resolve adjacent paths');
        }
        return Object.freeze({
            position: { current: currentIndex + 1, total: paths.length },
            previousLabel: i18n.t('contentPreview.actions.previousImage'),
            nextLabel: i18n.t('contentPreview.actions.nextImage'),
            previousLoadingPath: previousPath,
            nextLoadingPath: nextPath,
            onRequestPrevious: async (): Promise<void> => await this.#openAdjacent(-1),
            onRequestNext: async (): Promise<void> => await this.#openAdjacent(1)
        });
    }

    async #openAdjacent(direction: -1 | 1): Promise<void> {
        const paths = this.#getCurrentFolderImagePaths();
        if (paths.length <= 1) {
            return;
        }
        const currentPath = this.#host.getCurrentPath();
        if (!currentPath) {
            throw new Error('File Explorer image navigation requires an active image path');
        }
        const index = paths.indexOf(currentPath);
        if (index < 0) {
            return;
        }
        const nextIndex = (index + direction + paths.length) % paths.length;
        const nextPath = paths[nextIndex];
        if (!nextPath) {
            throw new Error('File Explorer image navigation resolved an empty target path');
        }
        await this.#host.openPath(nextPath, direction < 0 ? 'previous' : 'next');
    }

    #getCurrentFolderImagePaths(): readonly string[] {
        return uniqueStringsPreserveOrder(trimStringList(this.#host.getCurrentFolderImagePaths()));
    }
}

export { FileExplorerContentPreviewImageNavigationController };
export type { FileExplorerContentPreviewImageNavigationHost };
