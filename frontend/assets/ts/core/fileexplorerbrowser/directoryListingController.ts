/* SoAI - Shared frontend file explorer browser directory listing controller [frontend/assets/ts/core/fileexplorerbrowser/directoryListingController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { FileExplorerListingAcceptedResponse, FileExplorerListingLocateOptions, FileExplorerListingLocateResponse, FileExplorerListingPageOptions, FileExplorerListingPageResponse, FileExplorerListingReleasedResponse, FileExplorerListingSortColumn, FileExplorerListingSortDirection } from '@core/api/contracts/fileExplorerListingContractTypes.ts';
import type { FileExplorerSearchResponse } from '@core/api/contracts/fileExplorerContractTypes.ts';
import { ensureError, isErrorHttpStatus } from '@core/errors/coerce.ts';
import { parseFileBrowserEntriesPayload, parseFileBrowserLoadResponse } from '@core/fileexplorerbrowser/parsing.ts';
import { toVirtualPath } from '@core/fileexplorerbrowser/paths.ts';
import type { DirectoryListingBrowserState, FileBrowserErrorResolver } from '@core/fileexplorerbrowser/types.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';

interface DirectoryListingApi {
    startListing(listingId: string, path: string, signal?: AbortSignal): Promise<FileExplorerListingAcceptedResponse>;
    getListingPage(listingId: string, options: FileExplorerListingPageOptions): Promise<FileExplorerListingPageResponse>;
    locateListingEntry(listingId: string, name: string, options: FileExplorerListingLocateOptions): Promise<FileExplorerListingLocateResponse>;
    releaseListing(listingId: string, signal?: AbortSignal): Promise<FileExplorerListingReleasedResponse>;
    search(options: { path: string; query: string; limit: number; includeTotal: boolean; signal: AbortSignal }): Promise<FileExplorerSearchResponse>;
}

interface DirectoryListingControllerOptions {
    api: DirectoryListingApi;
    awaitTask: (taskId: string, signal: AbortSignal) => Promise<void>;
    errorResolver: FileBrowserErrorResolver;
    initialSort?: { column: FileExplorerListingSortColumn; direction: FileExplorerListingSortDirection };
    listingIdFactory?: () => string;
    onError?: (error: Error) => void;
    onStateChange: (state: DirectoryListingBrowserState) => void;
}

const PAGE_LIMIT = 400;

class DirectoryListingController {
    readonly #api: DirectoryListingApi;
    readonly #awaitTask: (taskId: string, signal: AbortSignal) => Promise<void>;
    readonly #errorResolver: FileBrowserErrorResolver;
    readonly #listingIdFactory: () => string;
    readonly #onError: ((error: Error) => void) | null;
    readonly #onStateChange: (state: DirectoryListingBrowserState) => void;
    #state: DirectoryListingBrowserState = {
        currentPath: '/',
        workspacePathResolved: null,
        query: '',
        entries: [],
        truncated: false,
        isLoading: false,
        errorMessage: null,
        sessionRevision: 0,
        total: 0,
        hasMore: false,
        nextOffset: null,
        isLoadingMore: false
    };
    #listingId: string | null = null;
    #sessionAbort: AbortController | null = null;
    #pageAbort: AbortController | null = null;
    #sequence = 0;
    #pageSequence = 0;
    #sortColumn: FileExplorerListingSortColumn = 'name';
    #sortDirection: FileExplorerListingSortDirection = 'asc';

    constructor(options: DirectoryListingControllerOptions) {
        this.#api = options.api;
        this.#awaitTask = options.awaitTask;
        this.#errorResolver = options.errorResolver;
        this.#listingIdFactory = options.listingIdFactory ?? (() => `listing-${crypto.randomUUID()}`);
        this.#onError = options.onError ?? null;
        this.#onStateChange = options.onStateChange;
        this.#sortColumn = options.initialSort?.column ?? 'name';
        this.#sortDirection = options.initialSort?.direction ?? 'asc';
    }

    destroy(): void {
        this.#sequence += 1;
        this.#sessionAbort?.abort();
        this.#pageAbort?.abort();
        this.#sessionAbort = null;
        this.#pageAbort = null;
        const listingId = this.#listingId;
        this.#listingId = null;
        if (listingId !== null) terminateHandledPromise(this.#api.releaseListing(listingId));
    }

    getState(): DirectoryListingBrowserState {
        return this.#state;
    }

    async initialize(path: string = '/'): Promise<void> {
        await this.navigate(path);
    }

    async refresh(): Promise<void> {
        await this.#load(this.#state.currentPath, this.#state.query);
    }

    async navigate(path: string): Promise<void> {
        await this.#load(toVirtualPath(path), '');
    }

    async search(query: string): Promise<void> {
        const normalizedQuery = query.trim();
        if (normalizedQuery === this.#state.query) return;
        await this.#load(this.#state.currentPath, normalizedQuery);
    }

    async clearSearch(): Promise<void> {
        if (!this.#state.query) return;
        await this.#load(this.#state.currentPath, '');
    }

    async setSort(sortColumn: FileExplorerListingSortColumn, sortDirection: FileExplorerListingSortDirection): Promise<void> {
        this.#sortColumn = sortColumn;
        this.#sortDirection = sortDirection;
        if (this.#state.query || this.#listingId === null) return;
        await this.#loadListingPage({ offset: 0, append: false });
    }

    async loadNextPage(): Promise<void> {
        if (this.#state.query || this.#state.isLoading || this.#state.isLoadingMore || !this.#state.hasMore || this.#state.nextOffset === null || this.#listingId === null) return;
        await this.#loadListingPage({ offset: this.#state.nextOffset, append: true });
    }

    async loadPageContaining(name: string): Promise<boolean> {
        if (this.#state.entries.some((entry) => entry.name === name)) return true;
        const listingId = this.#listingId;
        const sessionSignal = this.#sessionAbort?.signal;
        if (listingId === null || sessionSignal === undefined || this.#state.query) return false;
        this.#pageAbort?.abort();
        if (this.#state.isLoadingMore) this.#updateState({ isLoadingMore: false });
        const pageAbort = new AbortController();
        const pageSequence = ++this.#pageSequence;
        this.#pageAbort = pageAbort;
        let result: FileExplorerListingLocateResponse;
        try {
            result = await this.#api.locateListingEntry(listingId, name, {
                sortColumn: this.#sortColumn,
                sortDirection: this.#sortDirection,
                entryType: 'all',
                signal: pageAbort.signal
            });
        } catch (error) {
            if (pageAbort.signal.aborted || sessionSignal.aborted || pageSequence !== this.#pageSequence) return false;
            if (isErrorHttpStatus(error, 404)) return false;
            throw error;
        }
        if (pageAbort.signal.aborted || sessionSignal.aborted || pageSequence !== this.#pageSequence || listingId !== this.#listingId) return false;
        const pageOffset = Math.floor(result.offset / PAGE_LIMIT) * PAGE_LIMIT;
        while (this.#state.nextOffset !== null && this.#state.nextOffset <= pageOffset) {
            const nextOffset = this.#state.nextOffset;
            await this.#loadListingPage({ offset: nextOffset, append: true });
            if (sessionSignal.aborted || listingId !== this.#listingId) return false;
            if (this.#state.nextOffset === nextOffset) return false;
        }
        return this.#state.entries.some((entry) => entry.name === name);
    }

    async #load(currentPath: string, query: string): Promise<void> {
        this.#sessionAbort?.abort();
        this.#pageAbort?.abort();
        const sessionAbort = new AbortController();
        const sequence = ++this.#sequence;
        this.#sessionAbort = sessionAbort;
        const previousListingId = this.#listingId;
        this.#listingId = null;
        this.#updateState({
            currentPath,
            query,
            entries: [],
            isLoading: true,
            isLoadingMore: false,
            errorMessage: null,
            sessionRevision: sequence,
            total: 0,
            hasMore: false,
            nextOffset: null
        });
        try {
            if (previousListingId !== null) await this.#api.releaseListing(previousListingId);
            if (sessionAbort.signal.aborted || sequence !== this.#sequence) return;
            if (query) {
                await this.#loadSearch(currentPath, query, sessionAbort.signal, sequence);
                return;
            }
            const listingId = this.#listingIdFactory();
            this.#listingId = listingId;
            const admission = await this.#api.startListing(listingId, currentPath, sessionAbort.signal);
            await this.#awaitTask(admission.taskId, sessionAbort.signal);
            if (sessionAbort.signal.aborted || sequence !== this.#sequence || this.#listingId !== listingId) {
                terminateHandledPromise(this.#api.releaseListing(listingId));
                return;
            }
            await this.#loadListingPage({ offset: 0, append: false });
        } catch (error) {
            if (sessionAbort.signal.aborted || sequence !== this.#sequence) return;
            this.#applyError(ensureError(error), currentPath, query);
        }
    }

    async #loadSearch(currentPath: string, query: string, signal: AbortSignal, sequence: number): Promise<void> {
        const payload = await this.#api.search({ path: currentPath, query, limit: PAGE_LIMIT, includeTotal: false, signal });
        if (signal.aborted || sequence !== this.#sequence) return;
        const parsed = parseFileBrowserLoadResponse(payload, query);
        this.#updateState({
            currentPath: parsed.currentPath,
            workspacePathResolved: parsed.workspacePathResolved,
            query: parsed.query,
            entries: parsed.entries,
            truncated: parsed.truncated,
            isLoading: false,
            total: payload.total,
            hasMore: false,
            nextOffset: null
        });
    }

    async #loadListingPage(request: { offset: number; append: boolean }): Promise<void> {
        const listingId = this.#listingId;
        const sessionSignal = this.#sessionAbort?.signal;
        if (listingId === null || sessionSignal === undefined || sessionSignal.aborted) return;
        this.#pageAbort?.abort();
        const pageAbort = new AbortController();
        const pageSequence = ++this.#pageSequence;
        this.#pageAbort = pageAbort;
        if (request.append) {
            this.#updateState({ isLoadingMore: true });
        } else if (!this.#state.isLoading) {
            this.#updateState({ isLoading: true, entries: [], isLoadingMore: false });
        }
        try {
            const payload = await this.#api.getListingPage(listingId, {
                offset: request.offset,
                limit: PAGE_LIMIT,
                sortColumn: this.#sortColumn,
                sortDirection: this.#sortDirection,
                entryType: 'all',
                signal: pageAbort.signal
            });
            if (pageAbort.signal.aborted || sessionSignal.aborted || pageSequence !== this.#pageSequence || listingId !== this.#listingId) return;
            const entries = parseFileBrowserEntriesPayload(payload, payload.path, false);
            this.#updateState({
                currentPath: payload.path,
                workspacePathResolved: payload.workspacePathResolved,
                entries: request.append ? [...this.#state.entries, ...entries] : entries,
                truncated: payload.hasMore,
                isLoading: false,
                isLoadingMore: false,
                total: payload.total,
                hasMore: payload.hasMore,
                nextOffset: payload.nextOffset,
                errorMessage: null
            });
        } catch (error) {
            if (pageAbort.signal.aborted || sessionSignal.aborted || pageSequence !== this.#pageSequence) return;
            const resolvedError = ensureError(error);
            if (request.append) {
                this.#updateState({
                    isLoadingMore: false,
                    errorMessage: this.#errorResolver.resolve(resolvedError)
                });
                this.#onError?.(resolvedError);
                return;
            }
            this.#applyError(resolvedError, this.#state.currentPath, this.#state.query);
        }
    }

    #applyError(error: Error, currentPath: string, query: string): void {
        this.#updateState({
            currentPath,
            query,
            entries: [],
            truncated: false,
            isLoading: false,
            isLoadingMore: false,
            errorMessage: this.#errorResolver.resolve(error),
            total: 0,
            hasMore: false,
            nextOffset: null
        });
        this.#onError?.(error);
    }

    #updateState(patch: Partial<DirectoryListingBrowserState>): void {
        this.#state = { ...this.#state, ...patch };
        this.#onStateChange(this.#state);
    }
}

export { DirectoryListingController };
export type { DirectoryListingApi, DirectoryListingControllerOptions };
