/* SoAI - File explorer page control layer content preview request controller [frontend/assets/ts/pages/fileexplorer/controllers/FileExplorerContentPreviewRequestController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

class FileExplorerContentPreviewRequestController {
    #sequence = 0;
    #path: string | null = null;
    #abort = new AbortController();

    normalizePath(path: string, message: string): string {
        const normalized = path.trim();
        if (!normalized) {
            throw new Error(message);
        }
        return normalized;
    }

    signal(): AbortSignal {
        return this.#abort.signal;
    }

    begin(path: string): number {
        this.#abort.abort();
        this.#abort = new AbortController();
        this.#sequence += 1;
        this.#path = path;
        return this.#sequence;
    }

    isCurrent(sequence: number): boolean {
        return sequence === this.#sequence;
    }

    currentPath(): string | null {
        return this.#path;
    }

    setCurrentPath(path: string | null): void {
        this.#path = path;
    }

    clear(): void {
        this.#abort.abort();
        this.#sequence += 1;
        this.#path = null;
    }
}

export { FileExplorerContentPreviewRequestController };
