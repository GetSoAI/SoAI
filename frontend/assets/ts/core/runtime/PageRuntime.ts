/* SoAI - Page lifecycle pipeline execution [frontend/assets/ts/core/runtime/PageRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { getAbortControllerCtor, requirePerformanceNow } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { formatCompactMillisecondsAsSecondsUnit } from '@core/primitives/duration.ts';
import { signalAborted } from '@core/lifecycle/abortSignals.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import type { MetricsContext, PageRuntimeOptions, PageRuntimePhases, PipelineTask, TimingPoint } from '@core/runtime/pageRuntimeContracts.ts';
import { PageRuntimePipeline } from '@core/runtime/pageRuntimePipeline.ts';
import { isFunction, isObject, isUndefined } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { claimErrorReporting } from '@core/errors/reportingOwnership.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
const PIPELINE_TIMEOUT_MS = 60000;

const createAbortController = (): AbortController => new (getAbortControllerCtor())();
const readAbortSignal = (controller: AbortController): AbortSignal => {
    if (!isObject(controller) || isUndefined(controller.signal)) {
        throw new Error('AbortController signal is required');
    }
    return controller.signal;
};
class PageRuntime {
    #readyPromise: Promise<void>;
    #viewReadyPromise: Promise<void>;
    #preparedPromise: Promise<void>;
    #pipelineTasks = new Set<Promise<void>>();
    pageId: string;
    metricsReporter: ((points: TimingPoint[], context: MetricsContext) => void) | null;
    currentTask: PipelineTask | null;
    constructor({ pageId, metricsReporter }: PageRuntimeOptions) {
        if (!pageId) {
            throw new Error('PageRuntime requires a page identifier');
        }
        this.pageId = pageId;
        this.metricsReporter = isFunction(metricsReporter) ? metricsReporter : null;
        this.currentTask = null;
        this.#readyPromise = Promise.resolve();
        this.#viewReadyPromise = Promise.resolve();
        this.#preparedPromise = Promise.resolve();
    }
    #failTask(task: PipelineTask, error: Error): void {
        if (task.isSettled) {
            return;
        }
        task.isSettled = true;
        task.failureError = error;
        task.prepared.reject(error);
        task.reveal.reject(error);
        task.viewReady.reject(error);
        task.ready.reject(error);
    }
    #succeedTask(task: PipelineTask): void {
        if (task.isSettled) {
            return;
        }
        task.isSettled = true;
        task.prepared.resolve(undefined);
        task.reveal.resolve(undefined);
        task.viewReady.resolve(undefined);
        task.ready.resolve(undefined);
    }
    #clearTaskTimeout(task: PipelineTask): void {
        if (task.timeoutId !== undefined) {
            clearTimeout(task.timeoutId);
            delete task.timeoutId;
        }
    }
    #armTaskTimeout(task: PipelineTask): void {
        this.#clearTaskTimeout(task);
        const getTimestamp = requirePerformanceNow();
        const startTime = getTimestamp();
        task.timeoutId = setTimeout(() => {
            if (this.currentTask !== task || signalAborted(task.signal)) {
                return;
            }
            const elapsed = getTimestamp() - startTime;
            const elapsedLabel = formatCompactMillisecondsAsSecondsUnit(elapsed);
            const limitLabel = formatCompactMillisecondsAsSecondsUnit(PIPELINE_TIMEOUT_MS);
            const error = new Error(`PageRuntime pipeline timeout at ${task.stage} after ${elapsedLabel} (limit: ${limitLabel})`);
            if (claimErrorReporting(error)) {
                errorHandler.error(this.pageId, 'Pipeline timeout - aborting', error);
            }
            this.#failTask(task, error);
            this.cancel('timeout');
        }, PIPELINE_TIMEOUT_MS);
    }
    start(parameters: JsonObject, phases: PageRuntimePhases): Promise<void> {
        this.#validatePhases(phases);
        this.cancel();
        const controller = createAbortController();
        const signal = readAbortSignal(controller);
        const ready = createDeferred<void>();
        const viewReady = createDeferred<void>();
        const prepared = createDeferred<void>();
        const reveal = createDeferred<void>();
        this.currentTask = {
            controller,
            signal,
            prepared,
            reveal,
            ready,
            viewReady,
            failureError: null,
            stage: 'start',
            isSettled: false
        };
        const task = this.currentTask;
        if (task) {
            this.#armTaskTimeout(task);
        }
        this.#viewReadyPromise = viewReady.promise;
        this.#readyPromise = ready.promise;
        this.#preparedPromise = prepared.promise;
        const attachUnhandledRejectionLogger = (label: string, promise: Promise<void>): void => {
            void promise.catch((error) => {
                const runtimeError = ensureError(error);
                errorHandler.debug(this.pageId, `PageRuntime ${label} promise rejected`, runtimeError);
            });
        };
        attachUnhandledRejectionLogger('viewReady', this.#viewReadyPromise);
        attachUnhandledRejectionLogger('ready', this.#readyPromise);
        attachUnhandledRejectionLogger('prepared', this.#preparedPromise);
        attachUnhandledRejectionLogger('reveal', reveal.promise);
        const pipeline = new PageRuntimePipeline({
            pageId: this.pageId,
            phases,
            metricsReporter: this.metricsReporter,
            getCurrentTask: () => this.currentTask,
            failTask: (activeTask, error) => this.#failTask(activeTask, error),
            succeedTask: (activeTask) => this.#succeedTask(activeTask),
            suspendTaskTimeout: (activeTask) => this.#clearTaskTimeout(activeTask),
            clearCurrentTask: (activeTask) => this.#clearCurrentTask(activeTask)
        });
        const executePipeline = async (): Promise<void> => {
            try {
                await pipeline.execute(parameters);
            } catch (error) {
                if (!signalAborted(signal)) {
                    const runtimeError = ensureError(error);
                    if (claimErrorReporting(runtimeError)) {
                        errorHandler.error(this.pageId, 'PageRuntime pipeline fatal error', runtimeError);
                    }
                }
            }
        };
        const pipelineTask = executePipeline().finally(() => this.#pipelineTasks.delete(pipelineTask));
        this.#pipelineTasks.add(pipelineTask);
        terminateHandledPromise(pipelineTask);
        return this.#readyPromise;
    }
    #validatePhases(phases: PageRuntimePhases): void {
        if (!isObject(phases)) {
            throw new Error('PageRuntime requires lifecycle phases');
        }
        const requiredPhases: (keyof PageRuntimePhases)[] = ['prepare', 'afterReveal'];
        for (const phase of requiredPhases) {
            if (!isFunction(phases[phase])) {
                throw new Error(`PageRuntime phase "${phase}" must be a function`);
            }
        }
    }
    cancel(reason?: string): void {
        const task = this.currentTask;
        if (!task) {
            this.#readyPromise = this.#viewReadyPromise = this.#preparedPromise = Promise.resolve();
            return;
        }
        this.currentTask = null;
        this.#clearTaskTimeout(task);
        const { controller } = task;
        try {
            if (controller && isFunction(controller.abort)) {
                controller.abort(reason);
            } else if (controller) {
                throw new Error('Abort controller must expose abort');
            }
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.debug(this.pageId, 'PageRuntime cancellation failed', runtimeError);
        }
        if (task.failureError) {
            this.#failTask(task, task.failureError);
        } else {
            this.#succeedTask(task);
        }
        this.#readyPromise = this.#viewReadyPromise = this.#preparedPromise = Promise.resolve();
    }
    whenReady({ waitForData = false, waitForReveal = true }: { waitForData?: boolean; waitForReveal?: boolean } = {}): Promise<void> {
        if (waitForReveal === false) {
            return this.#preparedPromise;
        }
        return waitForData ? this.#readyPromise : this.#viewReadyPromise;
    }
    currentSignal(): AbortSignal | null {
        return this.currentTask?.signal ?? null;
    }
    async settle(): Promise<void> {
        await Promise.all([...this.#pipelineTasks]);
    }
    allowReveal(): void {
        const task = this.currentTask;
        if (!task) {
            return;
        }
        this.#armTaskTimeout(task);
        task.reveal.resolve(undefined);
    }
    #clearCurrentTask(task: PipelineTask): void {
        if (this.currentTask === task) {
            this.currentTask = null;
        }
    }
}
export { PageRuntime };
export type { PageRuntimeOptions, PageRuntimePhases, TimingPoint, MetricsContext };
