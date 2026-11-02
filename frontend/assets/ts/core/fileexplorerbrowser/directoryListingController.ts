/* SoAI - Shared frontend file explorer browser directory listing controller [frontend/assets/ts/core/fileexplorerbrowser/directoryListingController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { FileExplorerListingSortColumn, FileExplorerListingSortDirection } from '@core/api/contracts/fileExplorerListingContractTypes.ts';
import type { DirectoryListingApi, DirectoryListingSnapshot, DirectoryListingSelection, DirectoryListingReleaseRecovery } from '@core/fileexplorerbrowser/directoryListingContracts.ts';
import { FILE_EXPLORER_LISTING_EXPIRED_ERROR_CODE } from '@core/api/contracts/fileExplorerListingContracts.ts';
import { ensureError, extractErrorCode } from '@core/errors/coerce.ts';
import { parseDirectorySearchSnapshot } from '@core/fileexplorerbrowser/parsing.ts';
import { toVirtualPath } from '@core/fileexplorerbrowser/paths.ts';
import type { DirectoryListingBrowserState, FileBrowserErrorResolver } from '@core/fileexplorerbrowser/types.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { DIRECTORY_LISTING_PAGE_LIMIT, DirectoryListingSession } from '@core/fileexplorerbrowser/directoryListingSession.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { resolveDirectoryListingFailureFreshness } from '@core/fileexplorerbrowser/directoryListingFailure.ts';
import { DirectoryListingReconciliation } from '@core/fileexplorerbrowser/directoryListingReconciliation.ts';
import { createAbortError, runWithAbortSignalScope, raceWithAbortSignal } from '@core/errors/abort.ts';
import { throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';

interface DirectoryListingControllerOptions {
    api: DirectoryListingApi;
    subscribeReleaseRecovery?: DirectoryListingReleaseRecovery;
    awaitTask: (taskId: string, signal: AbortSignal) => Promise<void>;
    errorResolver: FileBrowserErrorResolver;
    captureSelection?: () => DirectoryListingSelection;
    initialSort?: { column: FileExplorerListingSortColumn; direction: FileExplorerListingSortDirection };
    listingIdFactory?: () => string;
    onError?: (error: Error) => void;
    onStateChange: (state: DirectoryListingBrowserState) => void;
}

class DirectoryListingController {
    readonly #api: DirectoryListingApi;
    readonly #subscribeReleaseRecovery: DirectoryListingReleaseRecovery | undefined;
    readonly #awaitTask: (taskId: string, signal: AbortSignal) => Promise<void>;
    readonly #errorResolver: FileBrowserErrorResolver;
    readonly #listingIdFactory: () => string;
    readonly #onError: ((error: Error) => void) | null;
    readonly #onStateChange: (state: DirectoryListingBrowserState) => void;
    #state: DirectoryListingBrowserState = {
        updatedAtMs: null,
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
        isLoadingMore: false,
        freshness: 'current'
    };
    readonly #captureSelection: (() => DirectoryListingSelection) | null;
    readonly #reconciliation: DirectoryListingReconciliation;
    #listing: DirectoryListingSession | null = null;
    readonly #sessions = new Set<DirectoryListingSession>();
    #disposal: Promise<void> | null = null;
    #sessionAbort: AbortController | null = null;
    #sequence = 0;
    #sortColumn: FileExplorerListingSortColumn = 'name';
    #sortDirection: FileExplorerListingSortDirection = 'asc';

    constructor(options: DirectoryListingControllerOptions) {
        this.#api = options.api;
        this.#subscribeReleaseRecovery = options.subscribeReleaseRecovery;
        this.#captureSelection = options.captureSelection ?? null;
        this.#awaitTask = options.awaitTask;
        this.#errorResolver = options.errorResolver;
        this.#listingIdFactory = options.listingIdFactory ?? (() => generateSecureId('listing'));
        this.#onError = options.onError ?? null;
        this.#onStateChange = options.onStateChange;
        this.#sortColumn = options.initialSort?.column ?? 'name';
        this.#sortDirection = options.initialSort?.direction ?? 'asc';
        this.#reconciliation = new DirectoryListingReconciliation({
            replace: (signal, canCommit) => this.#load(this.#state.currentPath, this.#state.query, true, signal, canCommit),
            markStale: (recovering = false) => {
                if (!this.#disposal && this.#state.freshness !== 'unavailable' && this.#state.freshness !== 'stale') this.#updateState({ freshness: recovering && this.#state.freshness === 'current' ? 'refreshing' : 'stale' });
            },
            reportFailure: (error) => {
                if (!this.#disposal) {
                    this.#updateState({ freshness: resolveDirectoryListingFailureFreshness(error, this.#state.freshness), errorMessage: this.#errorResolver.resolve(error) });
                    this.#onError?.(error);
                }
            }
        });
    }

    destroy(): Promise<void> {
        if (this.#disposal) return this.#disposal;
        const completion = createDeferred<void>();
        this.#disposal = completion.promise;
        this.#sequence += 1;
        this.#reconciliation.dispose();
        const sessionAbort = this.#sessionAbort;
        this.#sessionAbort = null;
        this.#listing = null;
        sessionAbort?.abort();
        const dispose = async (): Promise<void> => {
            const outcomes = await Promise.allSettled(
                [...this.#sessions].map((session) => {
                    this.#retire(session);
                    return session.releaseCompletion;
                })
            );
            throwCollectedCleanupFailures(outcomes.flatMap((outcome) => (outcome.status === 'rejected' ? [ensureError(outcome.reason)] : [])));
        };
        void dispose().then(completion.resolve, (error) => completion.reject(ensureError(error)));
        return completion.promise;
    }

    #retire(session: DirectoryListingSession): void {
        if (session.releaseState === 'active') {
            terminateHandledPromise(
                session.releaseCompletion.then(
                    () => this.#sessions.delete(session),
                    () => undefined
                )
            );
        }
        terminateHandledPromise(
            session.release().catch((error) => {
                if (!this.#disposal) this.#onError?.(ensureError(error));
            })
        );
    }

    #recoverReleases(): void {
        for (const session of this.#sessions) if (session.releaseState === 'failed') this.#retire(session);
    }

    getState(): DirectoryListingBrowserState {
        return this.#state;
    }

    async initialize(path: string = '/'): Promise<void> {
        await this.navigate(path);
    }

    refresh(): Promise<boolean> {
        this.#recoverReleases();
        return this.#reconciliation.invalidate(true);
    }

    invalidate(): Promise<boolean> {
        return this.#reconciliation.invalidate();
    }

    async navigate(path: string): Promise<void> {
        this.#recoverReleases();
        await this.#reconciliation.read((canCommit) => this.#load(toVirtualPath(path), '', false, undefined, canCommit), true);
    }

    async search(query: string): Promise<void> {
        const normalizedQuery = query.trim();
        if (normalizedQuery === this.#state.query) return;
        this.#recoverReleases();
        await this.#reconciliation.read((canCommit) => this.#load(this.#state.currentPath, normalizedQuery, false, undefined, canCommit), true);
    }

    async clearSearch(): Promise<void> {
        if (!this.#state.query) return;
        await this.#reconciliation.read((canCommit) => this.#load(this.#state.currentPath, '', false, undefined, canCommit), true);
    }

    async setSort(sortColumn: FileExplorerListingSortColumn, sortDirection: FileExplorerListingSortDirection): Promise<void> {
        this.#sortColumn = sortColumn;
        this.#sortDirection = sortDirection;
        if (this.#state.query || this.#listing === null || (this.#state.isLoading && !this.#listing.hasPageRead)) return;
        await this.#reconciliation.read((canCommit) => this.#loadListingPage({ offset: 0, append: false }, 1, canCommit));
    }

    async loadNextPage(): Promise<void> {
        if (this.#state.query || this.#state.isLoading || this.#state.isLoadingMore || !this.#state.hasMore || this.#state.nextOffset === null || this.#listing === null) return;
        const offset = this.#state.nextOffset;
        await this.#reconciliation.read((canCommit) => this.#loadListingPage({ offset, append: true }, 1, canCommit));
    }

    async loadPageContaining(name: string): Promise<boolean> {
        if (this.#state.entries.some((entry) => entry.name === name)) return true;
        return await this.#reconciliation.read((canCommit) => this.#loadListingPage({ offset: 0, append: true, name }, 1, canCommit));
    }

    async #load(currentPath: string, query: string, passive = false, signal?: AbortSignal, canCommit: () => boolean = () => true): Promise<boolean> {
        if (this.#disposal) throw createAbortError('Disposed directory browser cannot navigate');
        const previousSessionAbort = this.#sessionAbort;
        const sessionAbort = new AbortController();
        const sequence = ++this.#sequence;
        this.#sessionAbort = sessionAbort;
        const previousListing = this.#listing;
        const retained = passive && !this.#state.isLoading && (Boolean(query) || (previousListing !== null && previousListing.snapshot !== null));
        if (!retained) {
            this.#listing = null;
            if (previousListing) this.#retire(previousListing);
        }
        previousSessionAbort?.abort();
        if (sessionAbort.signal.aborted || sequence !== this.#sequence) return false;
        this.#updateState(
            retained
                ? { freshness: this.#state.freshness === 'current' ? 'refreshing' : this.#state.freshness, isLoadingMore: false }
                : {
                      currentPath,
                      query,
                      entries: [],
                      isLoading: true,
                      isLoadingMore: false,
                      errorMessage: null,
                      sessionRevision: sequence,
                      total: 0,
                      hasMore: false,
                      nextOffset: null,
                      freshness: 'current'
                  }
        );
        let listing: DirectoryListingSession | null = null;
        return await runWithAbortSignalScope([sessionAbort.signal, signal], async (readSignal) => {
            try {
                if (sessionAbort.signal.aborted || sequence !== this.#sequence) return false;
                if (query) {
                    return await this.#loadSearch(currentPath, query, readSignal, sequence, canCommit);
                }
                const listingId = this.#listingIdFactory();
                if (sessionAbort.signal.aborted || sequence !== this.#sequence) return false;
                listing = new DirectoryListingSession({ id: listingId, path: currentPath, api: this.#api, subscribeReleaseRecovery: this.#subscribeReleaseRecovery });
                this.#sessions.add(listing);
                if (!retained) this.#listing = listing;
                const admission = await listing.start(readSignal);
                await raceWithAbortSignal(this.#awaitTask(admission.taskId, readSignal), readSignal);
                if (sessionAbort.signal.aborted || sequence !== this.#sequence || !canCommit()) {
                    this.#retire(listing);
                    return false;
                }
                if (retained) {
                    const selection = this.#captureSelection?.();
                    const read = listing.beginRead();
                    const snapshot = await raceWithAbortSignal(listing.readPrefix(this.#state.entries.length, this.#sort(), read, canCommit), readSignal);
                    const missing = await raceWithAbortSignal(listing.findMissing(selection?.paths ?? [], this.#sort(), read, canCommit), readSignal);
                    if (sessionAbort.signal.aborted || sequence !== this.#sequence || !canCommit()) {
                        this.#retire(listing);
                        return false;
                    }
                    this.#listing = listing;
                    if (previousListing) this.#retire(previousListing);
                    this.#updateState({ ...snapshot, truncated: snapshot.hasMore, isLoading: false, isLoadingMore: false, errorMessage: null, sessionRevision: sequence, freshness: 'current' });
                    if (sequence === this.#sequence && canCommit()) selection?.removeMissing(missing);
                } else return await this.#loadListingPage({ offset: 0, append: false }, 1, canCommit);
                return true;
            } catch (error) {
                if (sessionAbort.signal.aborted || sequence !== this.#sequence || !canCommit()) {
                    if (listing) this.#retire(listing);
                    return false;
                }
                if (retained) {
                    if (listing) this.#retire(listing);
                    const resolved = ensureError(error);
                    this.#updateState({ freshness: resolveDirectoryListingFailureFreshness(resolved, this.#state.freshness), errorMessage: this.#errorResolver.resolve(resolved) });
                    this.#onError?.(resolved);
                } else this.#applyError(ensureError(error));
                return false;
            }
        });
    }

    async #loadSearch(currentPath: string, query: string, signal: AbortSignal, sequence: number, canCommit: () => boolean): Promise<boolean> {
        const payload = await raceWithAbortSignal(this.#api.search({ path: currentPath, query, limit: DIRECTORY_LISTING_PAGE_LIMIT, includeTotal: false, signal }), signal);
        if (signal.aborted || sequence !== this.#sequence || !canCommit()) return false;
        this.#updateState(parseDirectorySearchSnapshot(payload, currentPath, query));
        return true;
    }

    #sort(): { sortColumn: FileExplorerListingSortColumn; sortDirection: FileExplorerListingSortDirection } {
        return { sortColumn: this.#sortColumn, sortDirection: this.#sortDirection };
    }

    async #loadListingPage(request: { offset: number; append: boolean; name?: string }, remainingRecoveryAttempts = 1, canCommit: () => boolean = () => true): Promise<boolean> {
        const listing = this.#listing;
        const sessionSignal = this.#sessionAbort?.signal;
        const sequence = this.#sequence;
        if (!listing || !sessionSignal || sessionSignal.aborted) return false;
        const read = listing.beginRead();
        const isCurrent = (): boolean => canCommit() && listing.isCurrentRead(read) && !sessionSignal.aborted && sequence === this.#sequence && listing === this.#listing;
        if (request.name !== undefined) this.#updateState({ isLoadingMore: false });
        else if (request.append) this.#updateState({ isLoadingMore: true });
        else if (!this.#state.isLoading) this.#updateState({ isLoadingMore: false, freshness: this.#state.freshness === 'current' ? 'refreshing' : this.#state.freshness });
        if (!isCurrent()) return false;
        const commit = (snapshot: DirectoryListingSnapshot): void => {
            if (isCurrent()) this.#updateState({ ...snapshot, truncated: snapshot.hasMore, isLoading: false, isLoadingMore: false, errorMessage: null, freshness: this.#state.freshness === 'refreshing' ? 'current' : this.#state.freshness });
        };
        try {
            if (request.name !== undefined) return await listing.readContaining(request.name, this.#sort(), read, commit);
            const snapshot = await listing.readPage(request.offset, request.append, this.#sort(), read);
            if (!isCurrent()) return false;
            commit(snapshot);
            return true;
        } catch (error) {
            if (!isCurrent()) return false;
            const resolvedError = ensureError(error);
            if (remainingRecoveryAttempts > 0 && listing.snapshot && extractErrorCode(resolvedError) === FILE_EXPLORER_LISTING_EXPIRED_ERROR_CODE) {
                const refreshed = await this.#load(this.#state.currentPath, this.#state.query, true, undefined, canCommit);
                if (refreshed && request.name !== undefined) return await this.#loadListingPage(request, remainingRecoveryAttempts - 1, canCommit);
            } else if (request.append || listing.snapshot) {
                this.#updateState({ freshness: resolveDirectoryListingFailureFreshness(resolvedError, this.#state.freshness), isLoadingMore: false, errorMessage: this.#errorResolver.resolve(resolvedError) });
                this.#onError?.(resolvedError);
            } else this.#applyError(resolvedError);
            return false;
        }
    }

    #applyError(error: Error): void {
        this.#updateState({
            freshness: resolveDirectoryListingFailureFreshness(error, this.#state.freshness),
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
export type { DirectoryListingControllerOptions };
