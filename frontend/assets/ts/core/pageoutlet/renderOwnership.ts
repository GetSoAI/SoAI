/* SoAI - Page outlet render identity and cancellation ownership [frontend/assets/ts/core/pageoutlet/renderOwnership.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createAbortError, createAbortSignalScope, isAbortError } from '@core/errors/abort.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { claimErrorReporting } from '@core/errors/reportingOwnership.ts';
import type { PageHostCommitOptions, PageInstance } from '@core/pagehost/types.ts';
import { awaitCommitWindow, awaitStageWithTimeout } from '@core/pageoutlet/actions.ts';
import { PAGE_OUTLET_RENDER_STAGES, READY_TIMEOUT_MS } from '@core/pageoutlet/constants.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { PageHostInstance } from '@core/pageoutlet/types.ts';
import { runCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';

interface PageOutletRenderScope {
    signal: AbortSignal;
    committed: boolean;
    expired: boolean;
    mountPublication: NonNullable<PageHostCommitOptions['mountPublication']>;
    finish(): void;
    expire(): void;
}

interface ActivePageOutletRender {
    token: symbol;
    controller: AbortController;
    cleanupSignalScope(): void;
}

interface PageOutletDisposal {
    readonly actual: Promise<void>;
    readonly disposition: { final: boolean; expired: boolean; phase: 'waiting' | 'released' };
}

class PageOutletRenderOwnership {
    #active: ActivePageOutletRender | null = null;
    #commit: { token: symbol; completion: Promise<void>; actual: Promise<void> } | null = null;
    #superseded: { page: PageInstance; settle: (() => void) | null } | null = null;
    #disposal: PageOutletDisposal | null = null;

    begin(token: symbol, callerSignal?: AbortSignal, publication?: PageHostCommitOptions['mountPublication']): PageOutletRenderScope {
        const predecessor = this.#active;
        const controller = new AbortController();
        const signalScope = createAbortSignalScope([callerSignal, controller.signal]);
        const active: ActivePageOutletRender = {
            token,
            controller,
            cleanupSignalScope: signalScope.cleanup
        };
        this.#active = active;
        if (predecessor) {
            predecessor.controller.abort('navigation-superseded');
            predecessor.cleanupSignalScope();
        }
        const scope: PageOutletRenderScope = {
            signal: signalScope.signal,
            committed: false,
            expired: false,
            mountPublication: {
                commit: () => {
                    publication?.commit();
                    scope.committed = true;
                },
                rollback: () => {
                    publication?.rollback();
                    scope.committed = false;
                }
            },
            expire: (): void => {
                scope.expired = true;
                controller.abort('resource-release-unconfirmed');
            },
            finish: (): void => {
                signalScope.cleanup();
                if (this.#active === active) {
                    this.#active = null;
                }
            }
        };
        return scope;
    }

    isActive(token: symbol): boolean {
        return this.#active?.token === token;
    }

    isCommitting(token?: symbol): boolean {
        return this.#commit !== null && (token === undefined || this.#commit.token === token);
    }

    retainSuperseded(page: PageInstance, settle: (() => void) | null = null): void {
        this.#superseded = { page, settle };
    }

    clearSuperseded(): void {
        this.#superseded = null;
    }

    settleSuperseded(current: PageInstance | null): boolean {
        const superseded = this.#superseded;
        if (!superseded || superseded.page !== current) return false;
        this.#superseded = null;
        superseded.settle?.();
        return true;
    }

    commit(token: symbol, task: () => Promise<void>, options: { component: string; timeoutMs: number; expire(): void }): Promise<void> {
        if (this.#commit || this.#disposal) throw new Error('Page outlet commit already owns resource release');
        let expired = false;
        const completion = this.#startCommit(token, task, () => expired);
        return awaitStageWithTimeout(
            () => completion,
            options.timeoutMs,
            token,
            options.component,
            PAGE_OUTLET_RENDER_STAGES.RELEASED,
            () => true,
            () => {
                expired = true;
                options.expire();
            }
        );
    }

    dispose(release: () => Promise<void>, finalize: () => void | Promise<void>, final: boolean, timeoutMs: number, renderOwner?: symbol): Promise<void> {
        if (renderOwner !== undefined && !this.isActive(renderOwner)) return Promise.reject(createAbortError());
        const existing = this.#disposal;
        if (existing && (!final || existing.disposition.final || existing.disposition.phase !== 'released')) {
            existing.disposition.final ||= final;
            return this.#waitForDisposal(existing, timeoutMs);
        }
        const previous = this.#commit?.completion;
        const disposition: { final: boolean; expired: boolean; phase: 'waiting' | 'released' } = { final, expired: false, phase: 'waiting' };
        const token = Symbol('page-outlet-disposal');
        const actual = this.#startCommit(
            token,
            async () => {
                if (previous) await previous;
                await release();
                if (disposition.final) await finalize();
                disposition.phase = 'released';
            },
            () => disposition.expired
        );
        const disposal = { actual, disposition };
        this.#disposal = disposal;
        terminateHandledPromise(
            actual.then(() => {
                if (this.#disposal === disposal) this.#disposal = null;
            })
        );
        if (renderOwner === undefined) this.cancelActive('destroy-current');
        return this.#waitForDisposal(disposal, timeoutMs);
    }

    whenReleased(): Promise<void> {
        return this.#disposal?.actual ?? this.#commit?.actual ?? Promise.resolve();
    }

    #waitForDisposal(disposal: PageOutletDisposal, timeoutMs: number): Promise<void> {
        return awaitStageWithTimeout(
            () => disposal.actual,
            timeoutMs,
            Symbol('page-disposal-wait'),
            'resource-release',
            PAGE_OUTLET_RENDER_STAGES.RELEASED,
            () => true,
            () => {
                disposal.disposition.expired = true;
            }
        );
    }

    #startCommit(token: symbol, task: () => Promise<void>, isExpired: () => boolean): Promise<void> {
        const barrier = createDeferred<void>();
        const completion = createDeferred<void>();
        const commit = { token, completion: barrier.promise, actual: completion.promise };
        this.#commit = commit;
        const finish = (): void => {
            if (this.#commit === commit) this.#commit = null;
            barrier.resolve();
        };
        void Promise.resolve()
            .then(task)
            .then(
                () => {
                    finish();
                    completion.resolve();
                },
                (error) => {
                    finish();
                    const failure = ensureError(error);
                    if (isExpired() && !isAbortError(failure) && claimErrorReporting(failure)) errorHandler.error('PageOutlet', 'Page resource release failed after its deadline', failure);
                    completion.reject(failure);
                }
            );
        return completion.promise;
    }

    waitForCommit(timeoutMs = READY_TIMEOUT_MS, signal?: AbortSignal): Promise<boolean> {
        if (!this.#commit && !this.#disposal) return Promise.resolve(!signal?.aborted);
        return awaitCommitWindow(
            awaitStageWithTimeout(
                async () => {
                    while (this.#commit || this.#disposal) {
                        const commit = this.#commit;
                        const disposal = this.#disposal;
                        if (commit) await commit.completion;
                        if (disposal) await disposal.actual;
                    }
                },
                timeoutMs,
                Symbol('page-commit-wait'),
                'resource-release',
                PAGE_OUTLET_RENDER_STAGES.RELEASED,
                () => true,
                () => {},
                signal
            ),
            signal
        );
    }

    cancel(token: symbol, reason: string): void {
        const active = this.#active;
        if (!active || active.token !== token) return;
        this.#active = null;
        active.controller.abort(reason);
        active.cleanupSignalScope();
    }

    cancelActive(reason: string): void {
        const active = this.#active;
        if (active) this.cancel(active.token, reason);
    }

    cancelRender(reason: string, host: PageHostInstance | null, visual: { cancel(): void } | null): void {
        if (this.isCommitting()) return;
        const active = this.#active;
        const prepared = host?.captureCancellation(reason, 'prepared');
        const failures: Error[] = [];
        if (active) runCleanupStepCollectingFailure(() => this.cancel(active.token, reason), failures);
        if (!this.#active) {
            const superseded = this.#superseded;
            this.#superseded = null;
            const settled = superseded !== null && superseded.page === host?.getCurrent()?.instance;
            if (settled) runCleanupStepCollectingFailure(() => superseded.settle?.(), failures);
            if (!this.#active) runCleanupStepCollectingFailure(() => visual?.cancel(), failures);
            if (settled && !this.#active) runCleanupStepCollectingFailure(() => host?.allowReveal(), failures);
        }
        runCleanupStepCollectingFailure(() => prepared?.cancel(), failures);
        throwCollectedCleanupFailures(failures);
    }
}

export { PageOutletRenderOwnership };
export type { PageOutletRenderScope };
