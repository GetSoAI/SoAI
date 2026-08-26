/* SoAI - Abortable no-overlap polling loop [frontend/assets/ts/core/concurrency/pollingLoop.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { getWindow } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { LifecycleScope } from '@core/lifecycle/lifecycleScope.ts';
import { sleepMsAbortable } from '@core/primitives/sleepMsAbortable.ts';

type PollingLoopDecision = 'continue' | 'stop';

interface PollingLoopStepContext {
    signal: AbortSignal;
    stop: (reason?: string) => void;
}

interface PollingLoopOptions {
    label: string;
    intervalMs: number;
    initialDelayMs?: number | undefined;
    timeoutMs?: number | null | undefined;
    signal?: AbortSignal | null | undefined;
    run: (context: PollingLoopStepContext) => Promise<PollingLoopDecision | void> | PollingLoopDecision | void;
    onError?: ((error: Error) => PollingLoopDecision | void) | undefined;
}

interface PollingLoopHandle {
    readonly signal: AbortSignal;
    stop(reason?: string): void;
}

const resolveDelay = (value: number | null | undefined): number => (Number.isFinite(value) ? Math.max(0, Number(value)) : 0);

const startPollingLoop = (options: PollingLoopOptions): PollingLoopHandle => {
    const scope = new LifecycleScope();
    const run = scope.begin(options.label);
    const windowRef = getWindow();
    let timeoutId: number | null = null;
    let stopped = false;

    const stop = (reason: string = `${options.label}-stop`): void => {
        if (stopped) {
            return;
        }
        stopped = true;
        if (timeoutId !== null) {
            windowRef.clearTimeout(timeoutId);
            timeoutId = null;
        }
        options.signal?.removeEventListener('abort', handleExternalAbort);
        scope.abort(reason);
    };

    const handleExternalAbort = (): void => stop(`${options.label}-external-abort`);

    if (options.signal?.aborted === true) {
        stop(`${options.label}-external-aborted`);
        return {
            signal: run.signal,
            stop
        };
    }

    options.signal?.addEventListener('abort', handleExternalAbort, { once: true });

    const timeoutMs = resolveDelay(options.timeoutMs);
    if (timeoutMs > 0) {
        timeoutId = windowRef.setTimeout(() => stop(`${options.label}-timeout`), timeoutMs);
    }

    const execute = async (includeInitialDelay: boolean): Promise<void> => {
        const initialDelayMs = resolveDelay(options.initialDelayMs);
        const intervalMs = resolveDelay(options.intervalMs);
        try {
            if (includeInitialDelay && initialDelayMs > 0) {
                await sleepMsAbortable(run.signal, initialDelayMs);
            }
            while (scope.isCurrent(run)) {
                const decision = await options.run({ signal: run.signal, stop });
                if (!scope.isCurrent(run)) {
                    return;
                }
                if (decision === 'stop') {
                    stop(`${options.label}-completed`);
                    return;
                }
                await sleepMsAbortable(run.signal, intervalMs);
            }
        } catch (error) {
            const runtimeError = ensureError(error);
            if (isAbortError(runtimeError) || !scope.isCurrent(run)) {
                return;
            }
            let decision: PollingLoopDecision | void;
            try {
                decision = options.onError?.(runtimeError) ?? 'stop';
            } catch (handlerError) {
                errorHandler.warn('PollingLoop', `${options.label} error handler failed`, ensureError(handlerError));
                stop(`${options.label}-error-handler`);
                return;
            }
            if (decision === 'continue' && scope.isCurrent(run)) {
                void sleepMsAbortable(run.signal, resolveDelay(options.intervalMs))
                    .then(() => execute(false))
                    .catch((retryError) => {
                        const runtimeError = ensureError(retryError);
                        if (!isAbortError(runtimeError)) {
                            errorHandler.warn('PollingLoop', `${options.label} retry scheduling failed`, runtimeError);
                        }
                    });
                return;
            }
            stop(`${options.label}-error`);
        }
    };

    terminateHandledPromise(execute(true));

    return {
        signal: run.signal,
        stop
    };
};

export { startPollingLoop };
export type { PollingLoopDecision, PollingLoopHandle, PollingLoopOptions, PollingLoopStepContext };
