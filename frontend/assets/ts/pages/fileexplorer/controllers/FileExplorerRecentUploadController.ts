/* SoAI - File Explorer recent upload marker controller [frontend/assets/ts/pages/fileexplorer/controllers/FileExplorerRecentUploadController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createRecentItemTracker } from '@core/collectionpage/recentItemTracker.ts';
import { parentVirtualPath, toVirtualPath } from '@core/fileexplorerbrowser/paths.ts';
import type { FileBrowserEntry } from '@core/fileexplorerbrowser/types.ts';
import type { FileExplorerBatchUploadResponse, FileExplorerUploadResponse } from '@core/api/contracts/fileExplorerContractTypes.ts';
import type { FileExplorerUploadMarkerSession } from '@pages/fileexplorer/types.ts';

class FileExplorerRecentUploadController {
    readonly #tracker = createRecentItemTracker();
    readonly #pendingRevealPaths = new Set<string>();
    #currentPath = '/';
    #listingSessionRevision = 0;
    #loadRevision = 0;
    #retainNextLoad = false;

    handleListingLoad(path: string, listingSessionRevision: number): void {
        if (listingSessionRevision === this.#listingSessionRevision) {
            return;
        }
        this.#listingSessionRevision = listingSessionRevision;
        this.#currentPath = toVirtualPath(path);
        if (this.#retainNextLoad) {
            this.#retainNextLoad = false;
            return;
        }
        this.#loadRevision += 1;
        this.#pendingRevealPaths.clear();
        this.#tracker.clear();
    }

    retainAcrossNextLoad(): void {
        this.#retainNextLoad = true;
    }

    beginUploadSession(): FileExplorerUploadMarkerSession {
        return {
            currentPath: this.#currentPath,
            revision: this.#loadRevision
        };
    }

    markCreatedPath(session: FileExplorerUploadMarkerSession, path: string): boolean {
        if (!this.isUploadSessionCurrent(session)) {
            return false;
        }
        const normalized = toVirtualPath(path);
        this.#pendingRevealPaths.add(normalized);
        this.#tracker.markMany([normalized]);
        return true;
    }

    markUploadResponse(session: FileExplorerUploadMarkerSession, response: FileExplorerUploadResponse | FileExplorerBatchUploadResponse): boolean {
        if (!this.isUploadSessionCurrent(session)) {
            return false;
        }
        const uploadedPaths = this.#collectUploadedPaths(response);
        if (uploadedPaths.length <= 0) {
            return false;
        }
        for (const uploadedPath of uploadedPaths) {
            this.#pendingRevealPaths.add(uploadedPath);
        }
        this.#tracker.markMany(uploadedPaths);
        return true;
    }

    isUploadSessionCurrent(session: FileExplorerUploadMarkerSession): boolean {
        return session.revision === this.#loadRevision && session.currentPath === this.#currentPath;
    }

    isEntryRecent(entry: FileBrowserEntry): boolean {
        const entryPath = toVirtualPath(entry.path);
        if (this.#tracker.isMarked(entryPath)) {
            return true;
        }
        if (!entry.isDirectory) {
            return false;
        }
        for (const uploadedPath of this.#tracker.listMarked()) {
            if (this.#isDescendantOf(uploadedPath, entryPath)) {
                return true;
            }
        }
        return false;
    }

    resolveRevealPathsForEntries(entries: readonly FileBrowserEntry[]): string[] {
        if (this.#pendingRevealPaths.size <= 0) {
            return [];
        }
        const paths: string[] = [];
        for (const entry of entries) {
            const entryPath = toVirtualPath(entry.path);
            if (this.#shouldRevealEntryPath(entryPath, entry.isDirectory)) {
                paths.push(entryPath);
            }
        }
        return paths;
    }

    consumeRevealPaths(paths: readonly string[]): void {
        if (paths.length > 0) {
            this.#deleteCoveredRevealPaths(paths);
        }
    }

    async revealPending(session: FileExplorerUploadMarkerSession, reveal: (path: string) => Promise<boolean>): Promise<void> {
        if (!this.isUploadSessionCurrent(session)) {
            return;
        }
        const visiblePaths = new Set<string>();
        for (const pendingPath of this.#pendingRevealPaths) {
            const visiblePath = this.#resolveVisiblePath(pendingPath);
            if (visiblePath !== null) {
                visiblePaths.add(visiblePath);
            }
        }
        for (const visiblePath of visiblePaths) {
            if (!this.isUploadSessionCurrent(session)) {
                return;
            }
            if (await reveal(visiblePath)) {
                return;
            }
        }
    }

    clear(): void {
        this.#listingSessionRevision = 0;
        this.#loadRevision += 1;
        this.#retainNextLoad = false;
        this.#pendingRevealPaths.clear();
        this.#tracker.clear();
    }

    #collectUploadedPaths(response: FileExplorerUploadResponse | FileExplorerBatchUploadResponse): string[] {
        const paths: string[] = [];
        if ('results' in response) {
            for (const result of response.results) {
                if (!result.success) {
                    continue;
                }
                paths.push(toVirtualPath(result.path));
            }
            return [...new Set(paths)];
        }
        paths.push(toVirtualPath(response.path));
        return [...new Set(paths)];
    }

    #isDescendantOf(path: string, parentPath: string): boolean {
        const normalizedPath = toVirtualPath(path);
        const normalizedParent = toVirtualPath(parentPath);
        let cursor = parentVirtualPath(normalizedPath);
        while (cursor !== '/') {
            if (cursor === normalizedParent) {
                return true;
            }
            cursor = parentVirtualPath(cursor);
        }
        return normalizedParent === '/';
    }

    #shouldRevealEntryPath(entryPath: string, isDirectory: boolean): boolean {
        if (this.#pendingRevealPaths.has(entryPath)) {
            return true;
        }
        if (!isDirectory) {
            return false;
        }
        for (const uploadedPath of this.#pendingRevealPaths) {
            if (this.#isDescendantOf(uploadedPath, entryPath)) {
                return true;
            }
        }
        return false;
    }

    #resolveVisiblePath(path: string): string | null {
        const normalizedPath = toVirtualPath(path);
        if (!this.#isDescendantOf(normalizedPath, this.#currentPath)) {
            return null;
        }
        let visiblePath = normalizedPath;
        while (parentVirtualPath(visiblePath) !== this.#currentPath) {
            visiblePath = parentVirtualPath(visiblePath);
        }
        return visiblePath;
    }

    #deleteCoveredRevealPaths(revealedPaths: readonly string[]): void {
        for (const pendingPath of this.#pendingRevealPaths) {
            for (const revealedPath of revealedPaths) {
                if (pendingPath === revealedPath || this.#isDescendantOf(pendingPath, revealedPath)) {
                    this.#pendingRevealPaths.delete(pendingPath);
                    break;
                }
            }
        }
    }
}

export { FileExplorerRecentUploadController };
