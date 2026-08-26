/* SoAI - Page lifecycle pipeline contracts [frontend/assets/ts/core/runtime/pageRuntimeContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { Deferred } from '@core/runtime/deferred.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

interface PageRuntimePhaseContext {
    signal: AbortSignal;
    setStage(stage: string): void;
}

interface PageRuntimePhases {
    prepare(parameters: JsonObject, context: PageRuntimePhaseContext): Promise<void>;
    afterReveal(context: { signal: AbortSignal }): Promise<void>;
}

interface PageRuntimeOptions {
    pageId: string;
    metricsReporter?: ((points: TimingPoint[], context: MetricsContext) => void) | null;
}

interface TimingPoint {
    stage: string;
    time: number;
}

interface MetricsContext {
    aborted?: boolean;
    error?: Error | null;
}

interface PipelineTask {
    controller: AbortController;
    signal: AbortSignal;
    prepared: Deferred<void>;
    reveal: Deferred<void>;
    ready: Deferred<void>;
    viewReady: Deferred<void>;
    failureError: Error | null;
    stage: string;
    isSettled: boolean;
    timeoutId?: ReturnType<typeof setTimeout>;
}

export type { MetricsContext, PageRuntimeOptions, PageRuntimePhaseContext, PageRuntimePhases, PipelineTask, TimingPoint };
