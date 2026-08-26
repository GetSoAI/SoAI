/* SoAI - Bounded finite resource reconciliation execution [frontend/assets/ts/core/realtime/streammanager/resources/resourceReconciliationExecution.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createAbortError, isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { QueuedResourceAttempt, ReconciliationPolicy, ResourceAttempt, ResourceReconciliationSnapshot } from '@core/realtime/streammanager/resources/resourceReconciliationTypes.ts';
import { createImmutableResourceValue } from '@core/realtime/streammanager/resources/resourceValue.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

type ResourceAttemptExecutionOutcome = Readonly<{ type: 'success'; value: JsonValue }> | Readonly<{ type: 'failed'; error: Error }> | Readonly<{ type: 'superseded' }>;

interface ResourceAttemptExecutionOptions {
    name: string;
    policy: ReconciliationPolicy;
    attempt: ResourceAttempt;
    ownsAttempt(attempt: ResourceAttempt): boolean;
    handleDeadline(attempt: ResourceAttempt): void;
}

const createResourceAttempt = (name: string, queued: QueuedResourceAttempt, snapshot: ResourceReconciliationSnapshot): ResourceAttempt => ({
    identity: Symbol(name),
    targetReconciliationRevision: queued.targetReconciliationRevision,
    transportEpoch: snapshot.transportEpoch,
    lifecycleGeneration: snapshot.lifecycleGeneration,
    configurationRevision: snapshot.configurationRevision,
    source: queued.source,
    controller: new AbortController(),
    executor: queued.executor,
    authoritative: true,
    cleanupTimer: null,
    promise: Promise.resolve()
});

const executeWithinDeadline = (options: ResourceAttemptExecutionOptions, remainingMs: number): Promise<JsonValue> =>
    new Promise<JsonValue>((resolve, reject) => {
        let settled = false;
        let deadlineExceeded = false;
        const settle = (callback: () => void): void => {
            if (settled) return;
            settled = true;
            window.clearTimeout(deadlineTimer);
            callback();
        };
        const deadlineTimer = window.setTimeout((): void => {
            deadlineExceeded = true;
            options.handleDeadline(options.attempt);
        }, remainingMs);
        Promise.resolve()
            .then(() => {
                if (!options.ownsAttempt(options.attempt) || options.attempt.controller.signal.aborted) throw createAbortError();
                return options.attempt.executor({
                    signal: options.attempt.controller.signal,
                    reconciliationRevision: options.attempt.targetReconciliationRevision,
                    transportEpoch: options.attempt.transportEpoch
                });
            })
            .then(
                (value): void =>
                    settle((): void => {
                        if (deadlineExceeded) reject(new Error(`Resource ${options.name} reconciliation deadline exceeded`));
                        else resolve(value);
                    }),
                (error): void =>
                    settle((): void => {
                        if (deadlineExceeded) reject(new Error(`Resource ${options.name} reconciliation deadline exceeded`));
                        else reject(error);
                    })
            );
    });

const executeResourceAttempt = async (options: ResourceAttemptExecutionOptions): Promise<ResourceAttemptExecutionOutcome> => {
    const startedAt = performance.now();
    let finalError = new Error(`Resource ${options.name} reconciliation failed`);
    for (let attemptNumber = 1; attemptNumber <= options.policy.maximumAttempts; attemptNumber += 1) {
        if (!options.ownsAttempt(options.attempt)) return Object.freeze({ type: 'superseded' });
        const remainingMs = options.policy.deadlineMs - (performance.now() - startedAt);
        if (remainingMs <= 0) {
            finalError = new Error(`Resource ${options.name} reconciliation deadline exceeded`);
            break;
        }
        if (attemptNumber > 1) options.attempt.controller = new AbortController();
        try {
            const value = await executeWithinDeadline(options, remainingMs);
            if (!options.ownsAttempt(options.attempt)) return Object.freeze({ type: 'superseded' });
            return Object.freeze({ type: 'success', value: createImmutableResourceValue(value) });
        } catch (error) {
            finalError = ensureError(error);
            if (!options.ownsAttempt(options.attempt)) return Object.freeze({ type: 'superseded' });
            if (isAbortError(finalError)) {
                if (options.attempt.controller.signal.aborted) return Object.freeze({ type: 'superseded' });
                return Object.freeze({ type: 'failed', error: finalError });
            }
        }
    }
    return Object.freeze({ type: 'failed', error: finalError });
};

export { createResourceAttempt, executeResourceAttempt };
export type { ResourceAttemptExecutionOutcome };
