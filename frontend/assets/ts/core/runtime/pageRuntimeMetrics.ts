/* SoAI - Page lifecycle timing metrics [frontend/assets/ts/core/runtime/pageRuntimeMetrics.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dispatchCustomEvent, requirePerformanceNow } from '@core/environment/public.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

type TimingPoint = { stage: string; time: number };
type MetricsContext = { aborted?: boolean; error?: Error | null };

const reportPageRuntimeLifecycleMetrics = ({ pageId, points, context, metricsReporter }: { pageId: string; points: TimingPoint[]; context: MetricsContext; metricsReporter: ((points: TimingPoint[], context: MetricsContext) => void) | null }): void => {
    if (!points || points.length === 0) {
        return;
    }
    const segments: { stage: string; duration: number }[] = [];
    for (let index = 1; index < points.length; index++) {
        const prev = points[index - 1];
        const current = points[index];
        if (!prev || !current) {
            continue;
        }
        segments.push({
            stage: current.stage,
            duration: Math.max(0, current.time - prev.time)
        });
    }
    const timestamp = requirePerformanceNow()();
    const detail: Record<string, JsonValue | null | undefined> = {
        pageId,
        segments,
        totalDuration: segments.reduce((sum, entry) => sum + entry.duration, 0),
        aborted: Boolean(context && context.aborted),
        timestamp
    };
    if (context && context.error) {
        detail['error'] = { message: context.error.message || String(context.error) };
    }
    dispatchCustomEvent('soai:page:lifecycleTiming', detail);
    if (!metricsReporter) {
        return;
    }
    try {
        metricsReporter(points, context);
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.debug(pageId, 'PageRuntime metrics reporter failed', runtimeError);
    }
};

export { reportPageRuntimeLifecycleMetrics };
