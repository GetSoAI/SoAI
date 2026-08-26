/* SoAI - Charts feature viewport motion [frontend/assets/ts/features/charts/interaction/viewportMotion.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { monotonicMs } from '@core/time/clock.ts';
import type { RedrawRequest, SlotMetrics } from '@features/charts/component/chartComponentTypes.ts';
import type { ChartEventDetail } from '@features/charts/component/effects.ts';

type NumericIndexable = { length: number; [index: number]: number };

interface ViewportMotionHost {
    zoom: {
        startTime: number;
        startLevel: number;
        targetLevel: number;
        level: number;
        isAnimating: boolean;
    };
    chartOptions: {
        zoomEasingMs: number;
        onRequestHistoricalData?: ((timestamp: number) => void | Promise<void>) | null;
    };
    customBezierEasing: (currentTime: number, x1: number, y1: number, x2: number, y2: number) => number;
    pan: {
        isZooming: boolean;
        startOffset: number;
        targetOffset: number;
        offset: number;
        velocity: number;
        isAtTail: boolean;
    };
    clampPanOffset: () => void;
    requestRedraw: (options?: RedrawRequest) => void;
    getSlotMetrics: () => SlotMetrics;
    getMaxOffsetForMetrics: (metrics?: SlotMetrics | null | undefined) => number;
    isHistoricalDataLoading: boolean;
    dataLength: number;
    timestamps: NumericIndexable;
    lastHistoricalRequestTimestamp: number | null;
    chartEmit: (event: string, payload: ChartEventDetail) => void;
}

const applySmoothZoom = (host: ViewportMotionHost): void => {
    const progress = Math.min(1, (monotonicMs() - host.zoom.startTime) / host.chartOptions.zoomEasingMs);
    const eased = host.customBezierEasing(progress, 0.25, 0.1, 0.25, 1.0);
    host.zoom.level = host.zoom.startLevel + (host.zoom.targetLevel - host.zoom.startLevel) * eased;
    if (host.pan.isZooming) host.pan.offset = host.pan.startOffset + (host.pan.targetOffset - host.pan.startOffset) * eased;
    if (progress >= 1) {
        host.zoom.level = host.zoom.targetLevel;
        host.zoom.isAnimating = false;
        if (host.pan.isZooming) {
            host.pan.offset = host.pan.targetOffset;
            host.pan.isZooming = false;
        }
    }
    host.clampPanOffset();
    host.requestRedraw();
};

const applyInertialPanning = (host: ViewportMotionHost): void => {
    host.pan.velocity = clampNumber(host.pan.velocity, -50, 50);
    host.pan.offset += host.pan.velocity;
    host.pan.velocity *= 0.92 - Math.min(0.08, Math.abs(host.pan.velocity) * 0.012);
    if (Math.abs(host.pan.velocity) < 0.08) {
        const fraction = host.pan.offset - Math.floor(host.pan.offset);
        if (fraction < 0.3) host.pan.offset = Math.floor(host.pan.offset);
        else if (fraction > 0.7) host.pan.offset = Math.ceil(host.pan.offset);
        host.pan.velocity = 0;
    }
    host.clampPanOffset();
    host.requestRedraw();
};

const finishHistoricalDataRequest = (host: ViewportMotionHost): void => {
    host.isHistoricalDataLoading = false;
};

const reportHistoricalDataRequestError = (error: Error): void => {
    errorHandler.error('HistoryChart', 'Historical data request failed', error);
};

const trackHistoricalDataRequest = (host: ViewportMotionHost, task: Promise<void> | void): void => {
    Promise.resolve(task).then(
        () => {
            finishHistoricalDataRequest(host);
        },
        (error) => {
            finishHistoricalDataRequest(host);
            reportHistoricalDataRequestError(ensureError(error));
        }
    );
};

const clampPanOffset = (host: ViewportMotionHost): void => {
    const metrics = host.getSlotMetrics();
    const maxOffset = host.getMaxOffsetForMetrics(metrics);
    host.pan.offset = clampNumber(host.pan.offset, 0, maxOffset);
    host.pan.isAtTail = Math.abs(host.pan.offset - maxOffset) < 1e-3;
    if (host.pan.offset < 10 && !host.isHistoricalDataLoading && host.chartOptions.onRequestHistoricalData && host.dataLength > 0) {
        const timestamp = host.timestamps[0];
        const lastRequest = host.lastHistoricalRequestTimestamp;
        if (typeof timestamp !== 'number' || !Number.isFinite(timestamp)) return;
        const ts = timestamp;
        if (typeof lastRequest === 'number' && Number.isFinite(lastRequest) && Math.abs(ts - lastRequest) <= 1e-3) return;
        host.isHistoricalDataLoading = true;
        host.lastHistoricalRequestTimestamp = ts;
        host.chartEmit('needHistoricalData', { timestamp: ts });
        try {
            trackHistoricalDataRequest(host, host.chartOptions.onRequestHistoricalData(ts));
        } catch (error) {
            finishHistoricalDataRequest(host);
            reportHistoricalDataRequestError(ensureError(error));
        }
    }
};

export { applyInertialPanning, applySmoothZoom, clampPanOffset };
