/* SoAI - Page instance disposal completion and retained release ownership [frontend/assets/ts/core/pagehost/disposal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CLEANUP_METHODS } from '@core/pagehost/constants.ts';
import type { CleanupRunner, CurrentPageState, PageInstance, PageHostCommitOptions, PageHostOwnership } from '@core/pagehost/types.ts';
import type { PageContainerRollbackError } from '@core/pagehost/actions.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isThenable } from '@core/typeGuards.ts';
import { runCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';

class PageDisposal {
    readonly #tasks = new WeakMap<PageInstance, Promise<void>>();
    readonly #incomplete = new Map<PageInstance, { page: CurrentPageState; completion: Promise<void>; status: 'pending' | 'failed' }>();
    readonly #cleanupRunner: CleanupRunner;
    #commitCleanup: { completion: Promise<void>; status: 'pending' | 'failed'; pages: readonly CurrentPageState[] } | null = null;
    #committing: { pages: readonly CurrentPageState[] } | null = null;
    #failedCommit: { error: PageContainerRollbackError; pages: readonly CurrentPageState[] } | null = null;

    constructor(cleanupRunner: CleanupRunner) {
        this.#cleanupRunner = cleanupRunner;
    }

    cancelInstance(instance: PageInstance, reason: string): void {
        const controller = instance.abortController;
        const failures: Error[] = [];
        runCleanupStepCollectingFailure(() => instance.cancel?.(reason), failures);
        runCleanupStepCollectingFailure(() => controller?.abort(reason), failures);
        throwCollectedCleanupFailures(failures);
    }

    sealResources(pages: readonly CurrentPageState[]): void {
        const failures: Error[] = [];
        for (const page of pages) runCleanupStepCollectingFailure(() => page.instance.pageResources?.seal(), failures);
        throwCollectedCleanupFailures(failures);
    }

    get commitFailure(): PageContainerRollbackError | null {
        return this.#failedCommit?.error ?? null;
    }

    retainFailedCommit(error: PageContainerRollbackError, pages: readonly CurrentPageState[]): void {
        this.#failedCommit = { error, pages };
    }

    captureCommit(previous: CurrentPageState | null, prepared: CurrentPageState): () => void {
        const committing = { pages: previous ? [previous, prepared] : [prepared] };
        this.#committing = committing;
        return () => {
            if (this.#committing === committing) this.#committing = null;
        };
    }

    getOwnership(current: CurrentPageState | null, prepared: CurrentPageState | null, committing: boolean): PageHostOwnership {
        const retained = [...this.#incomplete.values()];
        const pages = [current, prepared, ...retained.map((entry) => entry.page), ...(this.#failedCommit?.pages ?? []), ...(this.#committing?.pages ?? []), ...(this.#commitCleanup?.pages ?? [])];
        const components = [...new Set(pages.filter((page): page is CurrentPageState => page !== null).map((page) => page.name))];
        const failed = this.#failedCommit !== null || retained.some((entry) => entry.status === 'failed') || this.#commitCleanup?.status === 'failed';
        const pending = committing || retained.length > 0 || this.#commitCleanup !== null;
        return { components, currentComponent: current?.name ?? null, release: failed ? 'failed' : pending ? 'pending' : 'settled' };
    }

    dispose(page: CurrentPageState, reason: string): Promise<void> {
        const existing = this.#tasks.get(page.instance);
        if (existing) return existing;
        const completion = createDeferred<void>();
        this.#tasks.set(page.instance, completion.promise);
        this.#incomplete.set(page.instance, { page, completion: completion.promise, status: 'pending' });
        const operation = this.#release(page, reason);
        void operation.then(
            () => {
                this.#incomplete.delete(page.instance);
                completion.resolve();
            },
            (error) => {
                const retained = this.#incomplete.get(page.instance);
                if (retained) retained.status = 'failed';
                completion.reject(ensureError(error));
            }
        );
        return completion.promise;
    }

    async waitForRelease(): Promise<void> {
        const tasks = [...this.#incomplete.values()].map((task) => task.completion);
        if (this.#commitCleanup) tasks.push(this.#commitCleanup.completion);
        const outcomes = await Promise.allSettled(tasks);
        const failures = outcomes.filter((outcome) => outcome.status === 'rejected').map((outcome) => ensureError(outcome.reason));
        if (failures.length) throw new AggregateError(failures, 'Page resource release incomplete');
    }

    async #release(page: CurrentPageState, reason: string): Promise<void> {
        const { instance, name, presentation } = page;
        const failures: Error[] = [];
        for (const operation of [() => this.sealResources([page]), () => this.cancelInstance(instance, reason), () => presentation.emit('changed'), () => instance.hide?.(), () => this.#cleanupRunner(instance, CLEANUP_METHODS)]) {
            try {
                const outcome = operation();
                if (isThenable(outcome)) await outcome;
            } catch (error) {
                failures.push(ensureError(error));
            }
        }
        if (failures.length) throw new AggregateError(failures, `Failed to release page ${name}`);
        page.releaseMutationAdmission?.();
        page.releaseMutationAdmission = null;
    }

    settleCommit(previous: CurrentPageState | null, previousContainer: HTMLElement, afterCommit: PageHostCommitOptions['afterCommit']): Promise<void> {
        const completion = createDeferred<void>();
        const retained: { completion: Promise<void>; status: 'pending' | 'failed'; pages: readonly CurrentPageState[] } = { completion: completion.promise, status: 'pending', pages: previous ? [previous] : [] };
        this.#commitCleanup = retained;
        const tasks: Promise<void>[] = [];
        if (previous) tasks.push(this.dispose(previous, 'navigation-commit'));
        try {
            tasks.push(Promise.resolve(afterCommit?.(previous ? previousContainer : null)));
        } catch (error) {
            tasks.push(Promise.reject(ensureError(error)));
        }
        void Promise.allSettled(tasks)
            .then((outcomes) => {
                const failures = outcomes.filter((outcome) => outcome.status === 'rejected').map((outcome) => ensureError(outcome.reason));
                if (failures.length) {
                    retained.status = 'failed';
                    completion.reject(new AggregateError(failures, 'Committed page cleanup incomplete'));
                } else {
                    if (this.#commitCleanup === retained) this.#commitCleanup = null;
                    completion.resolve();
                }
            })
            .catch((error) => {
                retained.status = 'failed';
                completion.reject(ensureError(error));
            });
        return completion.promise;
    }
}

export { PageDisposal };
