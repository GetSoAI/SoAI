/* SoAI - Charts feature viewport commands [frontend/assets/ts/features/charts/interaction/viewportCommands.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { isFunction } from '@core/typeGuards.ts';
import type { ChartInteractionScene } from '@features/charts/interaction/chartInteractionScene.ts';

type ZoomCommandOptions = {
    level: number;
    anchorRatio: number;
    source: string;
    animate: boolean;
};

const applyZoomAtRatio = (chart: ChartInteractionScene, options: ZoomCommandOptions): boolean => {
    const { zoom, pan } = chart.viewportState;
    const oldLevel = zoom.level;
    const newLevel = clampNumber(options.level, zoom.minLevel, zoom.maxLevel);
    if (Math.abs(newLevel - oldLevel) < 5e-5) {
        return false;
    }
    const anchorRatio = clampNumber(options.anchorRatio, 0, 1);
    const oldMetrics = chart.viewport.getSlotMetricsForLevel(oldLevel);
    const newMetrics = chart.viewport.getSlotMetricsForLevel(newLevel);
    const offsetDelta = (oldMetrics.dataSlots - newMetrics.dataSlots) * anchorRatio;
    const targetOffset = clampNumber(pan.offset + offsetDelta, 0, chart.viewport.getMaxOffsetForMetrics(newMetrics));
    pan.velocity = 0;

    if (options.animate && chart.configuration.options.enableSmoothZoom) {
        Object.assign(zoom, {
            startLevel: oldLevel,
            targetLevel: newLevel,
            startTime: monotonicMs(),
            isAnimating: true
        });
        Object.assign(pan, { startOffset: pan.offset, targetOffset, isZooming: true });
        chart.effects.scheduleFrame();
    } else {
        zoom.level = newLevel;
        zoom.targetLevel = newLevel;
        zoom.isAnimating = false;
        pan.offset = targetOffset;
        pan.targetOffset = targetOffset;
        pan.isZooming = false;
        chart.viewport.clampPanOffset();
        chart.effects.requestRedraw();
    }

    chart.effects.emit('zoomChange', { level: newLevel, oldLevel, source: options.source });
    const onZoomChange = chart.configuration.options.onZoomChange;
    if (isFunction(onZoomChange)) {
        onZoomChange(newLevel);
    }
    return true;
};

const panBySlots = (chart: ChartInteractionScene, slots: number): boolean => {
    if (!Number.isFinite(slots) || slots === 0) {
        return false;
    }
    const pan = chart.viewportState.pan;
    const nextOffset = clampNumber(pan.offset + slots, 0, chart.viewport.getMaxOffsetForMetrics());
    if (Math.abs(nextOffset - pan.offset) < 1e-6) {
        return false;
    }
    pan.offset = nextOffset;
    pan.targetOffset = nextOffset;
    pan.velocity = 0;
    chart.effects.requestRedraw();
    return true;
};

const resetViewport = (chart: ChartInteractionScene, alignToTail = false): void => {
    chart.viewport.resetZoom({ alignToTail });
};

const snapshotViewportToLatest = (chart: ChartInteractionScene): void => {
    chart.viewport.alignToLatest();
};

export { applyZoomAtRatio, panBySlots, resetViewport, snapshotViewportToLatest };
