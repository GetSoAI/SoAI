/* SoAI - File Explorer selection model (single source of truth) [frontend/assets/ts/pages/fileexplorer/state/FileExplorerSelectionState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toVirtualPath } from '@core/fileexplorerbrowser/paths.ts';
import type { FileExplorerSelectionSnapshot } from '@pages/fileexplorer/types.ts';

interface FileExplorerSelectionView {
    selectionCount: number;
    entryCount: number;
    isModeActive: boolean;
    allSelected: boolean;
    canOfferMode: boolean;
    canSelectAll: boolean;
    canDeselectAll: boolean;
    canInvert: boolean;
}

interface FileExplorerSelectionCapture {
    directoryGeneration: number;
    selectedPaths: ReadonlyMap<string, number>;
}

class FileExplorerSelectionModel {
    readonly #onChange: () => void;
    #selected: Set<string> = new Set();
    #entryPaths: string[] = [];
    #currentPath = '/';
    #revision = 0;
    #directoryGeneration = 0;
    #selectionSequence = 0;
    readonly #selectionTokens = new Map<string, number>();
    #modeRequested = false;
    #offerModeWhileLoading = false;

    constructor(dependencies: { onChange: () => void }) {
        this.#onChange = dependencies.onChange;
    }

    beginLoading(currentPath: string): void {
        this.#offerModeWhileLoading = toVirtualPath(currentPath) === this.#currentPath && (this.#entryPaths.length > 0 || this.#offerModeWhileLoading);
        this.#adoptListing(currentPath, []);
    }

    syncEntries(currentPath: string, entryPaths: readonly string[]): void {
        this.#offerModeWhileLoading = false;
        this.#adoptListing(
            currentPath,
            entryPaths.map((entryPath) => toVirtualPath(entryPath))
        );
    }

    requestMode(active: boolean): void {
        if (this.#modeRequested === active) {
            return;
        }
        this.#modeRequested = active;
        this.#onChange();
    }

    toggleMode(): void {
        if (this.#modeRequested || this.#selected.size > 0) {
            this.exitMode();
            return;
        }
        this.requestMode(true);
    }

    selectAll(): void {
        const selected = new Set(this.#selected);
        for (const entryPath of this.#entryPaths) {
            selected.add(entryPath);
        }
        this.#replaceSelection(selected);
    }

    deselectAll(): void {
        this.#replaceSelection(new Set());
    }

    exitMode(): void {
        this.#modeRequested = false;
        this.#replaceSelection(new Set());
    }

    invert(): void {
        const inverted = new Set(this.#selected);
        for (const entryPath of this.#entryPaths) {
            if (inverted.has(entryPath)) {
                inverted.delete(entryPath);
            } else {
                inverted.add(entryPath);
            }
        }
        this.#replaceSelection(inverted);
    }

    setPathSelected(path: string, selected: boolean): void {
        const normalized = toVirtualPath(path);
        if (this.#selected.has(normalized) === selected) {
            return;
        }
        const next = new Set(this.#selected);
        if (selected) {
            next.add(normalized);
        } else {
            next.delete(normalized);
        }
        this.#replaceSelection(next);
    }

    getSelectedPaths(): readonly string[] {
        return [...this.#selected.values()];
    }

    snapshot(): FileExplorerSelectionSnapshot {
        return {
            currentPath: this.#currentPath,
            revision: this.#revision,
            selectedPaths: this.getSelectedPaths()
        };
    }

    isSnapshotCurrent(snapshot: FileExplorerSelectionSnapshot): boolean {
        return snapshot.revision === this.#revision && snapshot.currentPath === this.#currentPath;
    }

    captureSelection(paths: readonly string[]): FileExplorerSelectionCapture {
        const selectedPaths = new Map<string, number>();
        for (const path of paths) {
            const normalized = toVirtualPath(path);
            const token = this.#selectionTokens.get(normalized);
            if (token !== undefined) selectedPaths.set(normalized, token);
        }
        return { directoryGeneration: this.#directoryGeneration, selectedPaths };
    }

    removeDeletedPaths(operation: FileExplorerSelectionCapture, paths: readonly string[]): void {
        if (operation.directoryGeneration !== this.#directoryGeneration) return;
        const selected = new Set(this.#selected);
        for (const path of paths) {
            const normalized = toVirtualPath(path);
            const capturedToken = operation.selectedPaths.get(normalized);
            if (capturedToken !== undefined && this.#selectionTokens.get(normalized) === capturedToken) {
                selected.delete(normalized);
            }
        }
        if (selected.size !== this.#selected.size) this.#replaceSelection(selected);
    }

    replaceRenamedPath(operation: FileExplorerSelectionCapture, sourcePath: string, destinationPath: string): void {
        if (operation.directoryGeneration !== this.#directoryGeneration) return;
        const source = toVirtualPath(sourcePath);
        const destination = toVirtualPath(destinationPath);
        const capturedToken = operation.selectedPaths.get(source);
        if (source === destination || capturedToken === undefined || this.#selectionTokens.get(source) !== capturedToken) return;
        const selected = new Set(this.#selected);
        selected.delete(source);
        selected.add(destination);
        this.#replaceSelection(selected);
    }

    view(): FileExplorerSelectionView {
        const entryCount = this.#entryPaths.length;
        const selectionCount = this.#selected.size;
        const allSelected = entryCount > 0 && this.#entryPaths.every((path) => this.#selected.has(path));
        const isModeActive = this.#modeRequested || selectionCount > 0;
        return {
            selectionCount,
            entryCount,
            isModeActive,
            allSelected,
            canOfferMode: entryCount > 0 || isModeActive || this.#offerModeWhileLoading,
            canSelectAll: isModeActive && entryCount > 0 && !allSelected,
            canDeselectAll: isModeActive && selectionCount > 0,
            canInvert: isModeActive && selectionCount > 0 && entryCount > 0 && !allSelected
        };
    }

    #adoptListing(currentPath: string, entryPaths: readonly string[]): void {
        const normalizedPath = toVirtualPath(currentPath);
        const pathChanged = normalizedPath !== this.#currentPath;
        if (pathChanged) {
            this.#modeRequested = false;
        }
        this.#currentPath = normalizedPath;
        this.#entryPaths = [...entryPaths];
        if (pathChanged) {
            this.#selected = new Set();
            this.#selectionTokens.clear();
            this.#directoryGeneration += 1;
        }
        this.#revision += 1;
        this.#onChange();
    }

    #replaceSelection(next: Set<string>): void {
        for (const path of this.#selected) {
            if (!next.has(path)) this.#selectionTokens.delete(path);
        }
        for (const path of next) {
            if (!this.#selected.has(path)) {
                this.#selectionSequence += 1;
                this.#selectionTokens.set(path, this.#selectionSequence);
            }
        }
        this.#selected = next;
        this.#revision += 1;
        this.#onChange();
    }
}

export { FileExplorerSelectionModel };
export type { FileExplorerSelectionCapture, FileExplorerSelectionView };
