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

class FileExplorerSelectionModel {
    readonly #onChange: () => void;
    #selected: Set<string> = new Set();
    #entryPaths: string[] = [];
    #currentPath = '/';
    #revision = 0;
    #modeRequested = false;

    constructor(dependencies: { onChange: () => void }) {
        this.#onChange = dependencies.onChange;
    }

    beginLoading(currentPath: string): void {
        this.#adoptListing(currentPath, []);
    }

    syncEntries(currentPath: string, entryPaths: readonly string[]): void {
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
            canOfferMode: entryCount > 0 || isModeActive,
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
        }
        this.#revision += 1;
        this.#onChange();
    }

    #replaceSelection(next: Set<string>): void {
        this.#selected = next;
        this.#revision += 1;
        this.#onChange();
    }
}

export { FileExplorerSelectionModel };
export type { FileExplorerSelectionView };
