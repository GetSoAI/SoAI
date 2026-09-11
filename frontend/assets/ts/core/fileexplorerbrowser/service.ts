/* SoAI - Shared file explorer browser service [frontend/assets/ts/core/fileexplorerbrowser/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { FileExplorerListResponse, FileExplorerSearchResponse } from '@core/api/contracts/fileExplorerContractTypes.ts';
import { raceWithAbortSignal } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { parseFileBrowserLoadResponse } from '@core/fileexplorerbrowser/parsing.ts';
import { resolveAbsolutePath, resolveVirtualPathFromAbsolute, toVirtualPath } from '@core/fileexplorerbrowser/paths.ts';
import type { DirectoryBrowserState, FileBrowserEntry, FileBrowserErrorResolver, FileBrowserSource } from '@core/fileexplorerbrowser/types.ts';
import { isJsonValue } from '@core/types/jsonValues.ts';

interface DirectoryBrowserControllerOptions {
    source: FileBrowserSource;
    entryFilter?: (entry: FileBrowserEntry) => boolean;
    errorResolver: FileBrowserErrorResolver;
    onError?: (error: Error) => void;
    onStateChange: (state: DirectoryBrowserState) => void;
}

interface DirectoryBrowserInitialization {
    initialVirtualPath?: string;
    initialAbsolutePath?: string;
}

interface ActiveOperation {
    abortController: AbortController;
    sequence: number;
}

class DirectoryBrowserController {
    readonly #source: FileBrowserSource;
    readonly #entryFilter: (entry: FileBrowserEntry) => boolean;
    readonly #errorResolver: FileBrowserErrorResolver;
    readonly #onError: ((error: Error) => void) | null;
    readonly #onStateChange: (state: DirectoryBrowserState) => void;
    #state: DirectoryBrowserState = {
        currentPath: '/',
        workspacePathResolved: null,
        query: '',
        entries: [],
        truncated: false,
        isLoading: false,
        errorMessage: null,
        rootPaths: [],
        pendingRootPath: null,
        canConfirm: false
    };
    #sequence = 0;
    #abort: AbortController | null = null;

    constructor(options: DirectoryBrowserControllerOptions) {
        this.#source = options.source;
        this.#entryFilter = options.entryFilter ?? (() => true);
        this.#errorResolver = options.errorResolver;
        this.#onError = options.onError ?? null;
        this.#onStateChange = options.onStateChange;
    }

    destroy(): void {
        this.#sequence += 1;
        this.#abort?.abort();
        this.#abort = null;
    }

    getSourceType(): FileBrowserSource['type'] {
        return this.#source.type;
    }

    getState(): DirectoryBrowserState {
        return this.#state;
    }

    async initialize(options: DirectoryBrowserInitialization = {}): Promise<void> {
        if (this.#source.type === 'host') {
            await this.#initializeHost(options.initialAbsolutePath);
            return;
        }
        await this.#loadWorkspace(toVirtualPath(options.initialVirtualPath ?? '/'), '');
    }

    async refresh(): Promise<void> {
        await this.#loadCommitted(this.#state.currentPath, this.#state.query);
    }

    async navigate(path: string): Promise<void> {
        await this.#loadCommitted(toVirtualPath(path), '');
    }

    async search(query: string): Promise<void> {
        const normalizedQuery = query.trim();
        if (normalizedQuery === this.#state.query && this.#state.errorMessage === null) return;
        await this.#loadCommitted(this.#state.currentPath, normalizedQuery);
    }

    async clearSearch(): Promise<void> {
        if (!this.#state.query && this.#state.errorMessage === null) return;
        await this.#loadCommitted(this.#state.currentPath, '');
    }

    async changeRoot(rootPath: string): Promise<void> {
        if (this.#source.type !== 'host') return;
        await this.#loadHost(rootPath, '/', '');
    }

    async locate(absolutePath: string): Promise<boolean> {
        if (this.#source.type !== 'host') return false;
        const operation = this.#startOperation(null);
        try {
            const located = await raceWithAbortSignal(this.#source.api.locate(absolutePath, { signal: operation.abortController.signal }), operation.abortController.signal);
            if (!this.#isCurrent(operation)) return false;
            const roots = this.#withRoot(this.#state.rootPaths, located.rootPath);
            this.#updateState({ rootPaths: roots, pendingRootPath: located.rootPath });
            const payload = await this.#requestHostLoad(located.rootPath, located.path, '', operation.abortController.signal);
            this.#commitLoad(operation, payload, '', roots, null, located.rootPath);
            return this.#isCurrent(operation);
        } catch (error) {
            this.#applyError(operation, ensureError(error));
        }
        return false;
    }

    async validateSelection(): Promise<boolean> {
        if (this.#source.type !== 'host') return this.#state.canConfirm;
        const rootPath = this.#state.workspacePathResolved;
        const absolutePath = resolveAbsolutePath(rootPath, this.#state.currentPath);
        if (!rootPath || !absolutePath) return false;
        const operation = this.#startOperation(null);
        try {
            const located = await raceWithAbortSignal(this.#source.api.locate(absolutePath, { signal: operation.abortController.signal }), operation.abortController.signal);
            if (!this.#isCurrent(operation)) return false;
            if (resolveVirtualPathFromAbsolute(rootPath, located.absolutePath) !== this.#state.currentPath || resolveVirtualPathFromAbsolute(located.rootPath, located.absolutePath) !== located.path) {
                throw new Error('Host directory validation returned an inconsistent location.');
            }
            this.#updateState({
                workspacePathResolved: located.rootPath,
                currentPath: located.path,
                rootPaths: this.#withRoot(this.#state.rootPaths, located.rootPath),
                pendingRootPath: null,
                isLoading: false,
                errorMessage: null,
                canConfirm: true
            });
            return true;
        } catch (error) {
            this.#applyError(operation, ensureError(error));
        }
        return false;
    }

    async #initializeHost(initialAbsolutePath: string | undefined): Promise<void> {
        if (this.#source.type !== 'host') return;
        const operation = this.#startOperation(null);
        try {
            const rootsResponse = await raceWithAbortSignal(this.#source.api.roots({ signal: operation.abortController.signal }), operation.abortController.signal);
            if (!this.#isCurrent(operation)) return;
            let roots: readonly string[] = rootsResponse.roots;
            let rootPath = rootsResponse.defaultRoot;
            let virtualPath = '/';
            let initialError: Error | null = null;
            if (initialAbsolutePath) {
                try {
                    const located = await raceWithAbortSignal(this.#source.api.locate(initialAbsolutePath, { signal: operation.abortController.signal }), operation.abortController.signal);
                    if (!this.#isCurrent(operation)) return;
                    rootPath = located.rootPath;
                    virtualPath = located.path;
                    roots = this.#withRoot(roots, rootPath);
                } catch (error) {
                    if (!this.#isCurrent(operation)) return;
                    initialError = ensureError(error);
                }
            }
            this.#updateState({ rootPaths: roots, pendingRootPath: rootPath });
            const payload = await this.#requestHostLoad(rootPath, virtualPath, '', operation.abortController.signal);
            this.#commitLoad(operation, payload, '', roots, initialError, rootPath);
        } catch (error) {
            this.#applyError(operation, ensureError(error));
        }
    }

    async #loadCommitted(currentPath: string, query: string): Promise<void> {
        if (this.#source.type === 'workspace') {
            await this.#loadWorkspace(currentPath, query);
            return;
        }
        const rootPath = this.#state.workspacePathResolved;
        if (!rootPath) {
            const operation = this.#startOperation(null);
            this.#applyError(operation, new Error('Host filesystem root is unavailable.'));
            return;
        }
        await this.#loadHost(rootPath, currentPath, query);
    }

    async #loadWorkspace(currentPath: string, query: string): Promise<void> {
        if (this.#source.type !== 'workspace') return;
        const operation = this.#startOperation(null);
        try {
            const request: Promise<FileExplorerListResponse | FileExplorerSearchResponse> = query ? this.#source.api.search({ path: currentPath, query, limit: 400, includeTotal: false, signal: operation.abortController.signal }) : this.#source.api.list({ path: currentPath, limit: 400, signal: operation.abortController.signal });
            const payload = await raceWithAbortSignal(request, operation.abortController.signal);
            this.#commitLoad(operation, payload, query, []);
        } catch (error) {
            this.#applyError(operation, ensureError(error));
        }
    }

    async #loadHost(rootPath: string, currentPath: string, query: string): Promise<void> {
        const operation = this.#startOperation(rootPath);
        try {
            const payload = await this.#requestHostLoad(rootPath, currentPath, query, operation.abortController.signal);
            this.#commitLoad(operation, payload, query, this.#state.rootPaths, null, rootPath);
        } catch (error) {
            this.#applyError(operation, ensureError(error));
        }
    }

    async #requestHostLoad(rootPath: string, currentPath: string, query: string, signal: AbortSignal): Promise<FileExplorerListResponse | FileExplorerSearchResponse> {
        if (this.#source.type !== 'host') throw new Error('Host browser source is required.');
        const request: Promise<FileExplorerListResponse | FileExplorerSearchResponse> = query ? this.#source.api.search({ rootPath, path: currentPath, query, limit: 400, includeTotal: false, signal }) : this.#source.api.list({ rootPath, path: currentPath, limit: 400, signal });
        return await raceWithAbortSignal(request, signal);
    }

    #startOperation(pendingRootPath: string | null): ActiveOperation {
        this.#abort?.abort();
        const abortController = new AbortController();
        const operation = { abortController, sequence: ++this.#sequence };
        this.#abort = abortController;
        this.#updateState({ isLoading: true, errorMessage: null, pendingRootPath });
        return operation;
    }

    #commitLoad(operation: ActiveOperation, payload: FileExplorerListResponse | FileExplorerSearchResponse, query: string, roots: readonly string[], retainedError: Error | null = null, expectedRoot: string | null = null): void {
        if (!this.#isCurrent(operation)) return;
        if (!isJsonValue(payload)) throw new Error('File browser response must be JSON-compatible');
        const parsed = parseFileBrowserLoadResponse(payload, query);
        if (expectedRoot !== null && resolveVirtualPathFromAbsolute(expectedRoot, parsed.workspacePathResolved ?? '') !== '/') {
            throw new Error('Host browser response root does not match the requested root.');
        }
        this.#updateState({
            currentPath: parsed.currentPath,
            workspacePathResolved: parsed.workspacePathResolved,
            query: parsed.query,
            entries: parsed.entries.filter(this.#entryFilter),
            truncated: parsed.truncated,
            rootPaths: roots,
            pendingRootPath: null,
            isLoading: false,
            errorMessage: retainedError ? this.#errorResolver.resolve(retainedError) : null,
            canConfirm: retainedError === null
        });
        if (retainedError) this.#onError?.(retainedError);
    }

    #applyError(operation: ActiveOperation, error: Error): void {
        if (!this.#isCurrent(operation)) return;
        this.#updateState({ isLoading: false, pendingRootPath: null, errorMessage: this.#errorResolver.resolve(error), canConfirm: false });
        this.#onError?.(error);
    }

    #isCurrent(operation: ActiveOperation): boolean {
        return !operation.abortController.signal.aborted && operation.sequence === this.#sequence;
    }

    #withRoot(roots: readonly string[], rootPath: string): readonly string[] {
        return roots.some((candidate) => resolveVirtualPathFromAbsolute(candidate, rootPath) === '/') ? roots : [...roots, rootPath];
    }

    #updateState(patch: Partial<DirectoryBrowserState>): void {
        this.#state = { ...this.#state, ...patch };
        this.#onStateChange(this.#state);
    }
}

export { DirectoryBrowserController };
export type { DirectoryBrowserControllerOptions, DirectoryBrowserInitialization };
