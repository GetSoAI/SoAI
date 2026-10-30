/* SoAI - Conversation find query, scan and freshness ownership [frontend/assets/ts/pages/chat/controllers/conversationfind/ConversationFindSearchController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createDeferred } from '@core/runtime/deferred.ts';
import { LatestRequestController } from '@core/concurrency/latestRequest.ts';
import { createAbortError, raceWithAbortSignal, runWithAbortSignalScope } from '@core/errors/abort.ts';
import { ensureError, isErrorHttpStatus } from '@core/errors/coerce.ts';
import { unicodeCodePointLength } from '@core/primitives/text.ts';
import { createLiteralSearchQuery } from '@core/search/literalOccurrences.ts';
import { normalizeSearchDisplayQuery } from '@core/search/searchQuery.ts';
import { monotonicMs, wallClockMs } from '@core/time/clock.ts';
import { ConversationFindResultIndex, ConversationSnapshotChangedError, preserveConversationFindTarget, mergeConversationFindResults, type ConversationFindEntry, type ConversationFindOverride, type ConversationFindScanResult, type ConversationFindTarget } from '@features/chat/public.ts';
import type { ConversationFindSearchContext, ConversationFindSearchDependencies, ConversationFindSearchSnapshot, ConversationFindSearchStatus } from '@pages/chat/controllers/conversationfind/contracts.ts';

class ConversationFindSearchController {
    readonly #dependencies: ConversationFindSearchDependencies;
    readonly #requests = new LatestRequestController();
    readonly #queries = new Map<string, string>();
    #generation = 0;
    #open = false;
    #conversationId: string | null = null;
    #query = '';
    #presentationKey = '';
    #status: ConversationFindSearchStatus = 'idle';
    #showSearching = false;
    #snapshot: ConversationFindScanResult | null = null;
    #index = new ConversationFindResultIndex([]);
    #target: ConversationFindTarget | null = null;
    #overrides: readonly ConversationFindOverride[] = [];
    #truncated = false;
    #needsRefill = false;
    #verifiedAt: number | null = null;
    #failure: ConversationFindSearchSnapshot['failure'] = null;
    #scanGeneration: number | null = null;
    #scanTask: Promise<void> | null = null;
    #refreshTimer: number | null = null;
    #waitForSettlement = false;
    #attemptedWhileExecuting = false;
    #connected = true;
    #disposed = false;

    constructor(dependencies: ConversationFindSearchDependencies) {
        this.#dependencies = dependencies;
    }

    get generation(): number {
        return this.#generation;
    }

    get snapshot(): ConversationFindSearchSnapshot {
        return { open: this.#open, query: this.#query, status: this.#status, showSearching: this.#showSearching, index: this.#index, target: this.#target, truncated: this.#truncated, needsRefill: this.#needsRefill, verifiedAt: this.#verifiedAt, failure: this.#failure };
    }

    isCurrent(generation: number): boolean {
        const context = this.#dependencies.captureContext();
        return !this.#disposed && this.#open && generation === this.#generation && context !== null && !context.signal.aborted && context.conversationId === this.#conversationId && context.presentationKey === this.#presentationKey && context.isCurrent();
    }

    open(prefill: string | null = null): boolean {
        if (this.#disposed) return false;
        const context = this.#dependencies.captureContext();
        if (context === null || context.signal.aborted || !context.isCurrent()) return false;
        this.#open = true;
        this.#conversationId = context.conversationId;
        this.#presentationKey = context.presentationKey;
        this.replaceQuery(prefill ?? this.#queries.get(context.conversationId) ?? '');
        return true;
    }

    replaceQuery(value: string): void {
        if (this.#disposed) return;
        this.#invalidate(true);
        this.#query = normalizeSearchDisplayQuery(value);
        this.#attemptedWhileExecuting = false;
        this.#waitForSettlement = false;
        this.#status = !this.#isQueryWithinLimit() ? 'too-long' : !this.#connected && this.#query ? 'stale' : 'idle';
        if (this.#conversationId !== null && this.#status !== 'too-long') this.#queries.set(this.#conversationId, this.#query);
        this.#dependencies.onChanged();
    }

    close(): void {
        if (!this.#open && this.#conversationId === null) return;
        this.#open = false;
        this.#invalidate(true);
        this.#conversationId = null;
        this.#query = '';
        this.#status = 'idle';
        this.#dependencies.onChanged();
    }

    dispose(): void {
        if (this.#disposed) return;
        this.#disposed = true;
        this.close();
        this.#queries.clear();
    }

    #isQueryWithinLimit(): boolean {
        return this.#query.length <= 256 || (this.#query.length <= 512 && unicodeCodePointLength(this.#query) <= 256);
    }

    pruneQueries(conversationIds: ReadonlySet<string>): void {
        for (const conversationId of this.#queries.keys()) if (!conversationIds.has(conversationId)) this.#queries.delete(conversationId);
        if (this.#conversationId !== null && !conversationIds.has(this.#conversationId)) this.close();
    }

    #invalidate(clearResults: boolean): void {
        this.#generation += 1;
        this.#requests.invalidate();
        this.#scanGeneration = null;
        this.#scanTask = null;
        this.#showSearching = false;
        this.#failure = null;
        if (this.#refreshTimer !== null) this.#dependencies.resources.clearTimer(this.#refreshTimer);
        this.#refreshTimer = null;
        if (clearResults) {
            this.#snapshot = null;
            this.#index = new ConversationFindResultIndex([]);
            this.#target = null;
            this.#overrides = [];
            this.#verifiedAt = null;
            this.#truncated = false;
            this.#needsRefill = false;
        }
        this.#dependencies.onInvalidated();
    }

    search(timeoutMs = 60_000): Promise<void> {
        const context = this.#dependencies.captureContext();
        if (!context || !this.isCurrent(this.#generation) || !this.#connected || !this.#query || !this.#isQueryWithinLimit()) {
            const idle = createDeferred<void>();
            idle.resolve();
            return idle.promise;
        }
        if (this.#scanGeneration === this.#generation && this.#scanTask !== null) return this.#scanTask;
        this.#scanGeneration = this.#generation;
        this.#scanTask = this.#executeSearch(this.#generation, context, Math.max(0, Math.min(timeoutMs, 60_000)));
        return this.#scanTask;
    }

    async #executeSearch(generation: number, context: ConversationFindSearchContext, timeoutMs: number): Promise<void> {
        const current = (): boolean => this.isCurrent(generation) && context.isCurrent();
        const deadlineController = new AbortController();
        const deadlineAt = monotonicMs() + timeoutMs;
        let deadlineExpired = false;
        const deadlineTimer = this.#dependencies.resources.setTimeout(() => {
            deadlineExpired = true;
            deadlineController.abort();
        }, timeoutMs);
        const presentationTimer = this.#dependencies.resources.setTimeout(() => {
            if (!current()) return;
            this.#showSearching = true;
            this.#dependencies.onChanged();
        }, 150);
        this.#status = this.#snapshot === null ? 'scanning' : 'updating';
        this.#failure = null;
        if (context.executionActive) this.#attemptedWhileExecuting = true;
        this.#dependencies.onChanged();
        try {
            await this.#requests.runLatest(
                async (request) =>
                    await runWithAbortSignalScope([request.signal, context.signal, deadlineController.signal], async (signal) => {
                        for (let attempt = 0; attempt < 2; attempt += 1) {
                            try {
                                const result = await raceWithAbortSignal(this.#dependencies.scan(createLiteralSearchQuery(this.#query), signal), signal);
                                if (!current()) return;
                                if (deadlineExpired || monotonicMs() >= deadlineAt) {
                                    deadlineExpired = true;
                                    throw createAbortError();
                                }
                                const authority = this.#dependencies.captureContext();
                                if (authority === null || result.revision < authority.revision) throw new ConversationSnapshotChangedError();
                                this.#snapshot = result;
                                this.#reconcile();
                                this.#verifiedAt = wallClockMs();
                                this.#status = 'ready';
                                this.#failure = null;
                                this.#waitForSettlement = false;
                                return;
                            } catch (error) {
                                if (!current()) return;
                                if (deadlineExpired) {
                                    this.#status = 'incomplete';
                                    this.#failure = 'deadline';
                                    return;
                                }
                                if (signal.aborted) return;
                                if (error instanceof ConversationSnapshotChangedError) {
                                    if (attempt === 0) continue;
                                    this.#status = 'updating';
                                    this.#failure = 'conflict';
                                    this.#waitForSettlement = true;
                                    return;
                                }
                                if ([401, 403, 404, 410].some((status) => isErrorHttpStatus(error, status))) {
                                    this.#invalidate(true);
                                    if (isErrorHttpStatus(error, 401)) this.#queries.clear();
                                    else this.#queries.delete(context.conversationId);
                                }
                                this.#status = 'error';
                                this.#failure = 'operation';
                                this.#dependencies.onChanged();
                                this.#dependencies.reportFailure(ensureError(error));
                                break;
                            }
                        }
                    })
            );
        } finally {
            this.#dependencies.resources.clearTimer(deadlineTimer);
            this.#dependencies.resources.clearTimer(presentationTimer);
            if (current() && this.#scanGeneration === generation) {
                this.#scanTask = null;
                this.#scanGeneration = null;
                this.#showSearching = false;
                this.#dependencies.onChanged();
            }
        }
    }

    #reconcile(): void {
        const reconciled = mergeConversationFindResults(this.#snapshot?.index.entries ?? [], this.#snapshot?.truncated ?? false, this.#overrides);
        this.#target = preserveConversationFindTarget(this.#index, reconciled.index, this.#target);
        this.#index = reconciled.index;
        this.#overrides = reconciled.overrides;
        this.#truncated = reconciled.truncated;
        this.#needsRefill = reconciled.needsRefill;
    }

    applyLiveEntries(generation: number, entries: readonly ConversationFindEntry[], mountedMessageIds: ReadonlySet<string>): void {
        if (!this.isCurrent(generation) || !this.#query || !this.#isQueryWithinLimit()) return;
        const overrides = new Map(this.#overrides.map((override) => [override.entry.semanticId, { ...override, mounted: mountedMessageIds.has(override.entry.messageId) || mountedMessageIds.has(override.entry.semanticId) }]));
        for (const entry of entries) {
            const baseline = this.#snapshot?.index.entries.find((candidate) => candidate.messageId === entry.messageId || candidate.semanticId === entry.semanticId);
            const previous = overrides.get(entry.semanticId);
            overrides.set(entry.semanticId, { entry, baselineSourceRevision: baseline?.sourceRevision ?? previous?.baselineSourceRevision ?? null, mounted: true });
        }
        this.#overrides = Array.from(overrides.values());
        if (this.#snapshot === null) return;
        this.#reconcile();
        this.#dependencies.onChanged();
    }

    selectTarget(target: ConversationFindTarget | null): void {
        if (!this.isCurrent(this.#generation)) return;
        if (target !== null && this.#index.ordinalOf(target) === null) return;
        if (this.#target?.messageId === target?.messageId && this.#target?.occurrenceIndex === target?.occurrenceIndex) return;
        this.#target = target;
        this.#dependencies.onChanged();
    }

    navigate(delta: number, wrap: boolean): ConversationFindTarget | null {
        if (!this.isCurrent(this.#generation) || !Number.isSafeInteger(delta)) return null;
        const count = this.#index.totalOccurrences;
        if (count === 0) return null;
        const ordinal = this.#target === null ? (delta < 0 ? count : -1) : (this.#index.ordinalOf(this.#target) ?? -1);
        const desired = ordinal + delta;
        const next = wrap ? ((desired % count) + count) % count : Math.max(0, Math.min(desired, count - 1));
        this.selectTarget(this.#index.targetAt(next));
        return this.#target;
    }

    observeAuthority(settledTransition = false): void {
        if (!this.#open) return;
        const context = this.#dependencies.captureContext();
        if (context === null || context.conversationId !== this.#conversationId) {
            this.close();
            return;
        }
        if (!context.executionActive) this.#attemptedWhileExecuting = false;
        const presentationChanged = context.presentationKey !== this.#presentationKey;
        if (!presentationChanged && !settledTransition && (this.#snapshot === null || context.revision <= this.#snapshot.revision)) return;
        if (presentationChanged) {
            this.#invalidate(false);
            this.#overrides = [];
            this.#presentationKey = context.presentationKey;
            this.#waitForSettlement = false;
        }
        if (!this.#query || !this.#isQueryWithinLimit() || !this.#connected) return;
        this.#status = 'updating';
        this.#dependencies.onChanged();
        if (!settledTransition && (this.#waitForSettlement || (context.executionActive && this.#attemptedWhileExecuting))) return;
        this.#requestRefresh();
    }

    setConnected(connected: boolean): void {
        if (this.#connected === connected) return;
        this.#connected = connected;
        if (!this.#open) return;
        this.#invalidate(false);
        this.#status = !this.#isQueryWithinLimit() ? 'too-long' : !this.#query ? 'idle' : connected ? 'updating' : 'stale';
        this.#dependencies.onChanged();
        if (connected && this.#query && this.#isQueryWithinLimit()) this.#requestRefresh();
    }

    #requestRefresh(): void {
        if (this.#refreshTimer !== null || this.#scanGeneration === this.#generation) return;
        const generation = this.#generation;
        const timerId = this.#dependencies.resources.setTimeout(() => {
            if (this.#refreshTimer !== timerId) return;
            this.#refreshTimer = null;
            if (this.isCurrent(generation)) this.#dependencies.runTask('chat:find:refresh', () => this.search());
        }, 0);
        this.#refreshTimer = timerId;
    }
}

export { ConversationFindSearchController };
