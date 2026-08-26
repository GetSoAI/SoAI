/* SoAI - File explorer page control layer initial content controller [frontend/assets/ts/pages/fileexplorer/controllers/page/FileExplorerInitialContentController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { throwIfAborted } from '@core/errors/abort.ts';

interface FileExplorerInitialContentDependencies {
    initialPath: string;
    highlightPath: string | null;
    initialSearch: string;
    isDisposed: () => boolean;
    runTask: (task: () => Promise<void>) => Promise<void>;
    initialize: (path: string) => Promise<void>;
    revealPath: (path: string) => Promise<boolean>;
    applyInitialSearch: (query: string) => Promise<void>;
    openPreview: () => Promise<void>;
}

class FileExplorerInitialContentController {
    readonly #dependencies: FileExplorerInitialContentDependencies;
    #initialReady: Promise<void> | null = null;

    constructor(dependencies: FileExplorerInitialContentDependencies) {
        this.#dependencies = dependencies;
    }

    prepare(signal: AbortSignal | null): Promise<void> {
        if (this.#initialReady) {
            return this.#initialReady;
        }
        const initialLoad = this.#dependencies.runTask(async () => {
            if (this.#dependencies.isDisposed()) {
                return;
            }
            throwIfAborted(signal);
            await this.#dependencies.initialize(this.#dependencies.initialPath);
            if (this.#dependencies.highlightPath !== null && !this.#dependencies.initialSearch) {
                await this.#dependencies.revealPath(this.#dependencies.highlightPath);
            }
            if (this.#dependencies.isDisposed()) {
                return;
            }
            throwIfAborted(signal);
            if (this.#dependencies.initialSearch) {
                await this.#dependencies.applyInitialSearch(this.#dependencies.initialSearch);
                if (this.#dependencies.isDisposed()) {
                    return;
                }
                throwIfAborted(signal);
            }
            await this.#dependencies.openPreview();
        });
        const trackedInitialLoad = initialLoad.finally(() => {
            if (this.#initialReady === trackedInitialLoad) {
                this.#initialReady = null;
            }
        });
        this.#initialReady = trackedInitialLoad;
        return trackedInitialLoad;
    }
}

export { FileExplorerInitialContentController };
export type { FileExplorerInitialContentDependencies };
