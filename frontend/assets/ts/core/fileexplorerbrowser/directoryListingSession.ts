/* SoAI - Listing admission observation and exact release ownership [frontend/assets/ts/core/fileexplorerbrowser/directoryListingSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { FileExplorerListingAcceptedResponse, FileExplorerListingSortColumn, FileExplorerListingSortDirection } from '@core/api/contracts/fileExplorerListingContractTypes.ts';
import type { DirectoryListingApi, DirectoryListingReleaseRecovery, DirectoryListingSnapshot } from '@core/fileexplorerbrowser/directoryListingContracts.ts';
import { APIError, isNetworkError, isRequestTimeoutError } from '@core/apiError.ts';
import { wallClockMs } from '@core/time/clock.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { createAbortError, raceWithAbortSignal, throwIfAborted } from '@core/errors/abort.ts';
import { DirectoryListingFailure } from '@core/fileexplorerbrowser/directoryListingFailure.ts';
import { FILE_EXPLORER_LISTING_EXPIRED_ERROR_CODE } from '@core/api/contracts/fileExplorerListingContracts.ts';
import { ensureError, extractErrorCode, isErrorHttpStatus } from '@core/errors/coerce.ts';
import { parseFileBrowserEntriesPayload } from '@core/fileexplorerbrowser/parsing.ts';
import { basenameVirtualPath, toVirtualPath } from '@core/fileexplorerbrowser/paths.ts';
import { LifecycleScope, type LifecycleRun } from '@core/lifecycle/lifecycleScope.ts';

interface DirectoryListingAdmission {
    readonly completion: Promise<FileExplorerListingAcceptedResponse>;
    status: 'pending' | 'settled';
}

interface DirectoryListingRelease {
    readonly completion: Promise<void>;
    status: 'pending' | 'released' | 'failed';
    retryable: boolean;
}

interface DirectoryListingSort {
    readonly sortColumn: FileExplorerListingSortColumn;
    readonly sortDirection: FileExplorerListingSortDirection;
}

const DIRECTORY_LISTING_PAGE_LIMIT = 400;
const isRecoverableListingRelease = (error: Error): boolean => isNetworkError(error) || isRequestTimeoutError(error) || (error instanceof APIError && (error.status === 408 || error.status === 429 || error.status >= 500));

class DirectoryListingSession {
    readonly id: string;
    readonly path: string;
    readonly #api: Omit<DirectoryListingApi, 'search'>;
    #admission: DirectoryListingAdmission | null = null;
    #release: DirectoryListingRelease | null = null;
    readonly #released = createDeferred<{ error: Error } | null>();
    readonly #subscribeRecovery: DirectoryListingReleaseRecovery | undefined;
    #cleanupRecovery: (() => void) | null = null;
    readonly #reads = new LifecycleScope();
    #snapshot: DirectoryListingSnapshot | null = null;

    constructor({ id, path, api, subscribeReleaseRecovery }: { readonly id: string; readonly path: string; readonly api: Omit<DirectoryListingApi, 'search'>; readonly subscribeReleaseRecovery?: DirectoryListingReleaseRecovery | undefined }) {
        this.id = id;
        this.path = path;
        this.#api = api;
        this.#subscribeRecovery = subscribeReleaseRecovery;
    }

    get releaseCompletion(): Promise<void> {
        return this.#released.promise.then((outcome) => {
            if (outcome) throw outcome.error;
        });
    }

    get releaseState(): 'active' | 'pending' | 'released' | 'failed' {
        return this.#release?.status ?? 'active';
    }

    beginRead(): LifecycleRun {
        if (this.#release) throw createAbortError('Released listing cannot read pages');
        return this.#reads.begin('listing-read-superseded');
    }

    isCurrentRead(read: LifecycleRun): boolean {
        return this.#release === null && this.#reads.isCurrent(read);
    }

    get snapshot(): DirectoryListingSnapshot | null {
        return this.#snapshot;
    }

    get hasPageRead(): boolean {
        return this.#reads.controller !== null;
    }

    #requireRead(read: LifecycleRun, isReconciliationCurrent?: () => boolean): void {
        if (!this.isCurrentRead(read) || isReconciliationCurrent?.() === false) throw createAbortError('Listing read was superseded');
    }

    async readPage(offset: number, append: boolean, sort: DirectoryListingSort, read: LifecycleRun): Promise<DirectoryListingSnapshot> {
        this.#requireRead(read);
        const previous = append ? this.#snapshot : null;
        if (append && (!previous || previous.nextOffset !== offset)) throw new DirectoryListingFailure('incoherent', 'Listing append has no contiguous prefix');
        const payload = await raceWithAbortSignal(this.#api.getListingPage(this.id, { offset, limit: DIRECTORY_LISTING_PAGE_LIMIT, ...sort, entryType: 'all', signal: read.signal }), read.signal);
        this.#requireRead(read);
        if (payload.listingId !== this.id || toVirtualPath(payload.path) !== this.path || payload.offset !== offset) throw new DirectoryListingFailure('incoherent', 'Listing page changed its directory or offset');
        if (previous && (payload.total !== previous.total || payload.workspacePathResolved !== previous.workspacePathResolved)) throw new DirectoryListingFailure('incoherent', 'Listing page changed its snapshot authority');
        if (payload.hasMore && (payload.nextOffset === null || payload.nextOffset <= offset)) throw new DirectoryListingFailure('incoherent', 'Listing page made no progress');
        const entries = parseFileBrowserEntriesPayload(payload, payload.path, false);
        const combined = previous ? [...previous.entries, ...entries] : entries;
        if (new Set(combined.map((entry) => entry.path)).size !== combined.length) throw new DirectoryListingFailure('incoherent', 'Listing snapshot contains duplicate entry identities');
        this.#snapshot = { updatedAtMs: this.#snapshot?.updatedAtMs ?? wallClockMs(), currentPath: payload.path, workspacePathResolved: payload.workspacePathResolved, entries: combined, total: payload.total, hasMore: payload.hasMore, nextOffset: payload.nextOffset };
        return this.#snapshot;
    }

    async readPrefix(minimumEntries: number, sort: DirectoryListingSort, read: LifecycleRun, isReconciliationCurrent: () => boolean): Promise<DirectoryListingSnapshot> {
        this.#requireRead(read, isReconciliationCurrent);
        let snapshot = await this.readPage(0, false, sort, read);
        while (snapshot.entries.length < Math.min(minimumEntries, snapshot.total) && snapshot.nextOffset !== null) {
            this.#requireRead(read, isReconciliationCurrent);
            snapshot = await this.readPage(snapshot.nextOffset, true, sort, read);
        }
        this.#requireRead(read, isReconciliationCurrent);
        if (snapshot.entries.length < Math.min(minimumEntries, snapshot.total)) throw new DirectoryListingFailure('incoherent', 'Listing could not establish the retained prefix');
        return snapshot;
    }

    async findMissing(paths: readonly string[], sort: DirectoryListingSort, read: LifecycleRun, isReconciliationCurrent: () => boolean): Promise<readonly string[]> {
        const missing: string[] = [];
        for (const path of paths) {
            this.#requireRead(read, isReconciliationCurrent);
            if (this.#snapshot?.entries.some((entry) => entry.path === path)) continue;
            if ((await this.#locate(basenameVirtualPath(path), sort, read)) === null) missing.push(path);
        }
        this.#requireRead(read, isReconciliationCurrent);
        return missing;
    }

    async #locate(name: string, sort: DirectoryListingSort, read: LifecycleRun): Promise<number | null> {
        this.#requireRead(read);
        try {
            const result = await raceWithAbortSignal(this.#api.locateListingEntry(this.id, name, { ...sort, entryType: 'all', signal: read.signal }), read.signal);
            this.#requireRead(read);
            return result.offset;
        } catch (error) {
            this.#requireRead(read);
            if (isErrorHttpStatus(error, 404) && extractErrorCode(error) !== FILE_EXPLORER_LISTING_EXPIRED_ERROR_CODE) return null;
            throw error;
        }
    }

    async readContaining(name: string, sort: DirectoryListingSort, read: LifecycleRun, onPage: (snapshot: DirectoryListingSnapshot) => void): Promise<boolean> {
        const offset = await this.#locate(name, sort, read);
        if (offset === null) return false;
        let snapshot = this.#snapshot;
        while (snapshot?.nextOffset !== null && snapshot?.nextOffset !== undefined && snapshot.nextOffset <= offset) {
            snapshot = await this.readPage(snapshot.nextOffset, true, sort, read);
            onPage(snapshot);
            this.#requireRead(read);
        }
        return snapshot?.entries.some((entry) => entry.name === name) ?? false;
    }

    async start(signal: AbortSignal): Promise<FileExplorerListingAcceptedResponse> {
        throwIfAborted(signal);
        if (this.#release) throw createAbortError('A released listing cannot acquire a snapshot');
        let admission = this.#admission;
        if (!admission) {
            const completion = createDeferred<FileExplorerListingAcceptedResponse>();
            const incoming: DirectoryListingAdmission = { completion: completion.promise, status: 'pending' };
            admission = incoming;
            this.#admission = incoming;
            try {
                void this.#api.startListing(this.id, this.path).then(
                    (response) => {
                        incoming.status = 'settled';
                        completion.resolve(response);
                    },
                    (error) => {
                        incoming.status = 'settled';
                        completion.reject(ensureError(error));
                    }
                );
            } catch (error) {
                incoming.status = 'settled';
                completion.reject(ensureError(error));
            }
        }
        const response = await raceWithAbortSignal(admission.completion, signal);
        if (response.listingId !== this.id || toVirtualPath(response.path) !== this.path) throw new DirectoryListingFailure('incoherent', 'Listing admission identity does not match');
        if (this.#release) throw createAbortError('Listing admission was released');
        return response;
    }

    release(): Promise<void> {
        if (this.#release && (this.#release.status !== 'failed' || !this.#release.retryable)) return this.#release.completion;
        const completion = createDeferred<void>();
        const release: DirectoryListingRelease = { completion: completion.promise, status: 'pending', retryable: false };
        this.#release = release;
        this.#reads.abort('listing-released');
        const admission = this.#admission;
        const pendingAdmission = admission?.status === 'pending';
        const finalize = async (): Promise<void> => {
            const deleteListing = async (): Promise<void> => {
                const response = await this.#api.releaseListing(this.id);
                if (response.listingId !== this.id || response.status !== 'released') throw new DirectoryListingFailure('incoherent', 'Listing release identity does not match');
            };
            const earlyRelease = Promise.resolve().then(deleteListing);
            if (admission && pendingAdmission) {
                const [early] = await Promise.allSettled([earlyRelease, admission.completion]);
                if (early?.status === 'rejected' && !isRecoverableListingRelease(ensureError(early.reason))) throw early.reason;
                await deleteListing();
            } else await earlyRelease;
        };
        void finalize().then(
            () => {
                release.status = 'released';
                this.#cleanupRecovery?.();
                this.#cleanupRecovery = null;
                this.#released.resolve(null);
                completion.resolve();
            },
            (error) => {
                let failure = ensureError(error);
                release.status = 'failed';
                release.retryable = isRecoverableListingRelease(failure);
                if (!release.retryable) {
                    this.#cleanupRecovery?.();
                    this.#cleanupRecovery = null;
                    this.#released.resolve({ error: failure });
                } else if (!this.#cleanupRecovery && this.#subscribeRecovery) {
                    try {
                        this.#cleanupRecovery = this.#subscribeRecovery(
                            () => {
                                terminateHandledPromise(this.release());
                            },
                            () => {
                                this.#cleanupRecovery?.();
                                this.#cleanupRecovery = null;
                                release.retryable = false;
                                this.#released.resolve({ error: new APIError(401, 'Listing release is unconfirmed after authentication ended') });
                            },
                            failure,
                            this.id
                        );
                    } catch (subscriptionError) {
                        failure = new AggregateError([failure, ensureError(subscriptionError)], 'Listing release recovery subscription failed');
                    }
                }
                completion.reject(failure);
            }
        );
        return completion.promise;
    }
}

export { DIRECTORY_LISTING_PAGE_LIMIT, DirectoryListingSession };
export type { DirectoryListingSort };
