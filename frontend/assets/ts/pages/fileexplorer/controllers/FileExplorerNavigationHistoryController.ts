/* SoAI - File Explorer directory navigation history [frontend/assets/ts/pages/fileexplorer/controllers/FileExplorerNavigationHistoryController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parentVirtualPath, toVirtualPath } from '@core/fileexplorerbrowser/paths.ts';

interface FileExplorerNavigationHistoryHost {
    navigate: (path: string) => Promise<void>;
    resetSearchOnNavigation: () => void;
}

interface FileExplorerNavigationHistoryButtons {
    home: HTMLButtonElement;
    previous: HTMLButtonElement;
    next: HTMLButtonElement;
    up: HTMLButtonElement;
}

interface FileExplorerNavigationTransition {
    type: 'direct' | 'history';
    targetPath: string;
    targetIndex: number | null;
}

class FileExplorerNavigationHistoryController {
    readonly #host: FileExplorerNavigationHistoryHost;
    readonly #buttons: FileExplorerNavigationHistoryButtons;
    #paths: string[] = [];
    #currentIndex = -1;
    #currentPath = '/';
    #isLoading = true;
    #transition: FileExplorerNavigationTransition | null = null;
    #disposed = false;

    constructor(dependencies: { host: FileExplorerNavigationHistoryHost; buttons: FileExplorerNavigationHistoryButtons }) {
        this.#host = dependencies.host;
        this.#buttons = dependencies.buttons;
        this.#syncButtons();
    }

    handleBrowserState(currentPath: string, isLoading: boolean): void {
        if (this.#disposed) {
            return;
        }
        this.#currentPath = toVirtualPath(currentPath);
        this.#isLoading = isLoading;
        if (!isLoading) {
            this.#commitTerminalPath(this.#currentPath);
        }
        this.#syncButtons();
    }

    async navigate(path: string): Promise<void> {
        const targetPath = toVirtualPath(path);
        if (this.#disposed || (!this.#isLoading && targetPath === this.#currentPath)) {
            return;
        }
        await this.#runTransition({ type: 'direct', targetPath, targetIndex: null });
    }

    async navigateHome(): Promise<void> {
        await this.navigate('/');
    }

    async navigateUp(): Promise<void> {
        if (this.#disposed || this.#isBusy() || this.#currentPath === '/') {
            return;
        }
        await this.navigate(parentVirtualPath(this.#currentPath));
    }

    async navigatePrevious(): Promise<void> {
        if (this.#disposed || this.#isBusy() || this.#currentIndex <= 0) {
            return;
        }
        const targetIndex = this.#currentIndex - 1;
        const targetPath = this.#paths[targetIndex];
        if (targetPath === undefined) {
            throw new Error('File Explorer previous history entry is unavailable');
        }
        await this.#runTransition({ type: 'history', targetPath, targetIndex });
    }

    async navigateNext(): Promise<void> {
        if (this.#disposed || this.#isBusy() || this.#currentIndex >= this.#paths.length - 1) {
            return;
        }
        const targetIndex = this.#currentIndex + 1;
        const targetPath = this.#paths[targetIndex];
        if (targetPath === undefined) {
            throw new Error('File Explorer next history entry is unavailable');
        }
        await this.#runTransition({ type: 'history', targetPath, targetIndex });
    }

    destroy(): void {
        this.#disposed = true;
        this.#transition = null;
        this.#paths = [];
        this.#currentIndex = -1;
        this.#syncButtons();
    }

    async #runTransition(transition: FileExplorerNavigationTransition): Promise<void> {
        this.#transition = transition;
        this.#host.resetSearchOnNavigation();
        this.#syncButtons();
        try {
            await this.#host.navigate(transition.targetPath);
        } finally {
            if (this.#transition === transition && !this.#isLoading) {
                this.#transition = null;
                this.#syncButtons();
            }
        }
    }

    #commitTerminalPath(path: string): void {
        if (this.#paths.length === 0) {
            this.#paths = [path];
            this.#currentIndex = 0;
            this.#transition = null;
            return;
        }
        const transition = this.#transition;
        if (transition?.type === 'history' && transition.targetIndex !== null && transition.targetPath === path) {
            this.#currentIndex = transition.targetIndex;
            this.#transition = null;
            return;
        }
        const currentHistoryPath = this.#paths[this.#currentIndex];
        if (currentHistoryPath !== path) {
            this.#paths = this.#paths.slice(0, this.#currentIndex + 1);
            this.#paths.push(path);
            this.#currentIndex = this.#paths.length - 1;
        }
        this.#transition = null;
    }

    #isBusy(): boolean {
        return this.#isLoading || this.#transition !== null;
    }

    #syncButtons(): void {
        const busy = this.#disposed || this.#isBusy();
        this.#buttons.home.disabled = busy || this.#currentPath === '/';
        this.#buttons.up.disabled = busy || this.#currentPath === '/';
        this.#buttons.previous.disabled = busy || this.#currentIndex <= 0;
        this.#buttons.next.disabled = busy || this.#currentIndex < 0 || this.#currentIndex >= this.#paths.length - 1;
    }
}

export { FileExplorerNavigationHistoryController };
export type { FileExplorerNavigationHistoryButtons, FileExplorerNavigationHistoryHost };
