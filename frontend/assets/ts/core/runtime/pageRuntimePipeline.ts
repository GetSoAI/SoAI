/* SoAI - Page lifecycle stage pipeline [frontend/assets/ts/core/runtime/pageRuntimePipeline.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { requirePerformanceNow } from '@core/environment/public.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { claimErrorReporting } from '@core/errors/reportingOwnership.ts';
import { signalAborted } from '@core/lifecycle/abortSignals.ts';
import type { MetricsContext, PageRuntimePhases, PipelineTask, TimingPoint } from '@core/runtime/pageRuntimeContracts.ts';
import { reportPageRuntimeLifecycleMetrics } from '@core/runtime/pageRuntimeMetrics.ts';
import { isThenable } from '@core/typeGuards.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

interface PageRuntimePipelineOptions {
    pageId: string;
    phases: PageRuntimePhases;
    metricsReporter: ((points: TimingPoint[], context: MetricsContext) => void) | null;
    getCurrentTask: () => PipelineTask | null;
    failTask: (task: PipelineTask, error: Error) => void;
    succeedTask: (task: PipelineTask) => void;
    suspendTaskTimeout: (task: PipelineTask) => void;
    clearCurrentTask: (task: PipelineTask) => void;
}

const ensureAsyncResult = (result: Promise<void> | void, label: string): Promise<void> => {
    if (!isThenable(result)) {
        throw new Error(`${label} must return a Promise`);
    }
    return Promise.resolve(result).then(() => undefined);
};

class PageRuntimePipeline {
    readonly #options: PageRuntimePipelineOptions;

    constructor(options: PageRuntimePipelineOptions) {
        this.#options = options;
    }

    async execute(parameters: JsonObject): Promise<void> {
        const task = this.#options.getCurrentTask();
        if (!task) {
            errorHandler.warn(this.#options.pageId, 'PageRuntime pipeline called without an active task');
            return;
        }
        const timingPoints: TimingPoint[] = [];
        const getTimestamp = requirePerformanceNow();
        let currentStage = 'start';
        const markStage = (label: string): void => {
            const lastPoint = timingPoints[timingPoints.length - 1];
            if (!label || (lastPoint && lastPoint.stage === label)) {
                return;
            }
            currentStage = label;
            task.stage = label;
            timingPoints.push({ stage: label, time: getTimestamp() });
        };
        markStage('start');
        let pipelineError: Error | null = null;
        try {
            await this.#runLifecycle(parameters, task, markStage);
        } catch (error) {
            const runtimeError = ensureError(error);
            pipelineError = runtimeError;
            if (signalAborted(task.signal) || task.failureError || task.isSettled) {
                return;
            }
            this.#options.failTask(task, runtimeError);
            const failureStage = currentStage;
            markStage('error');
            if (claimErrorReporting(runtimeError)) {
                errorHandler.error(this.#options.pageId, `Page readiness pipeline failed at stage: ${failureStage}`, runtimeError);
            }
        } finally {
            this.#finalize(task, timingPoints, markStage, pipelineError);
        }
    }

    async #runLifecycle(parameters: JsonObject, task: PipelineTask, markStage: (label: string) => void): Promise<void> {
        const { signal, prepared, ready, reveal, viewReady } = task;
        markStage('pipelineStart');
        if (signalAborted(signal)) {
            return;
        }
        await ensureAsyncResult(this.#options.phases.prepare(parameters, { signal, setStage: markStage }), 'prepare');
        if (signalAborted(signal)) {
            return;
        }
        this.#options.suspendTaskTimeout(task);
        prepared.resolve(undefined);
        markStage('prepared');
        await reveal.promise;
        markStage('revealAllowed');
        if (signalAborted(signal)) {
            return;
        }
        await ensureAsyncResult(this.#options.phases.afterReveal({ signal }), 'afterReveal');
        markStage('afterPageReveal');
        if (signalAborted(signal)) {
            return;
        }
        viewReady.resolve(undefined);
        markStage('viewReady');
        if (!signalAborted(signal)) {
            ready.resolve(undefined);
            task.isSettled = true;
            markStage('ready');
        }
    }

    #finalize(task: PipelineTask, timingPoints: TimingPoint[], markStage: (label: string) => void, pipelineError: Error | null): void {
        this.#options.suspendTaskTimeout(task);
        if (signalAborted(task.signal) && !task.failureError && !task.isSettled) {
            this.#options.succeedTask(task);
            markStage('aborted');
        }
        this.#options.clearCurrentTask(task);
        markStage('complete');
        reportPageRuntimeLifecycleMetrics({
            pageId: this.#options.pageId,
            points: timingPoints,
            metricsReporter: this.#options.metricsReporter,
            context: {
                aborted: signalAborted(task.signal),
                error: pipelineError ?? task.failureError
            }
        });
    }
}

export { PageRuntimePipeline };
