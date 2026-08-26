/* SoAI - Charts feature interaction effects [frontend/assets/ts/features/charts/interaction/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import { hideCrosshair } from '@features/charts/crosshair.ts';
import type { ChartInteractionScene } from '@features/charts/interaction/chartInteractionScene.ts';
import { getPinchMetrics, resolveFirstTwoPointers } from '@features/charts/guards.ts';
import { handleMouseDown } from '@features/charts/interaction/actions.ts';
import { requirePointerState, resetDragState } from '@features/charts/interaction/state.ts';
import { applyZoomAtRatio } from '@features/charts/interaction/viewportCommands.ts';
import type { PointerRecord } from '@features/charts/types.ts';

const PINCH_ZOOM_RESPONSE_EXPONENT = 1.75;

const beginPinchGesture = (chart: ChartInteractionScene): void => {
    const state = requirePointerState(chart);
    if (state.activePointers.size < 2) {
        return;
    }
    const pair = resolveFirstTwoPointers(state);
    if (!pair) {
        throw new Error('Chart pinch gesture requires two valid active pointers');
    }
    const [pointer1, pointer2] = pair;
    const { dist, cx, cy } = getPinchMetrics(pointer1, pointer2);
    const dimensions = chart.viewport.getChartDimensions();
    if (dimensions.chartWidth <= 0) {
        throw new Error('Chart pinch gesture requires a positive chart width');
    }
    const anchorRatio = clampNumber((cx - dimensions.left) / dimensions.chartWidth, 0, 1);

    state.pinch = {
        initialDistance: dist,
        initialZoom: chart.viewportState.zoom.level,
        centerX: cx,
        centerY: cy,
        startDistance: dist,
        startLevel: chart.viewportState.zoom.level,
        anchorRatio,
        lastCenterX: cx,
        lastCenterY: cy
    };
    chart.viewport.markManual('pinch');
    resetDragState(chart);
    hideCrosshair(chart);
};

const updatePinchGesture = (chart: ChartInteractionScene): void => {
    const state = requirePointerState(chart);
    if (!state.pinch || state.activePointers.size < 2) {
        return;
    }
    const pinchState = state.pinch;
    const pair = resolveFirstTwoPointers(state);
    if (!pair) {
        throw new Error('Chart pinch update requires two valid active pointers');
    }
    const [pointer1, pointer2] = pair;
    const { dist: currentDistance, cx } = getPinchMetrics(pointer1, pointer2);
    const dimensions = chart.viewport.getChartDimensions();
    const storedAnchorRatio = pinchState.anchorRatio;
    const storedStartLevel = pinchState.startLevel;
    const storedLastCenterX = pinchState.lastCenterX;
    if (typeof storedAnchorRatio !== 'number' || !Number.isFinite(storedAnchorRatio) || typeof storedStartLevel !== 'number' || !Number.isFinite(storedStartLevel) || typeof storedLastCenterX !== 'number' || !Number.isFinite(storedLastCenterX)) {
        throw new Error('Chart pinch state requires finite anchor, start level, and last center');
    }
    if (dimensions.chartWidth <= 0) {
        throw new Error('Chart pinch update requires a positive chart width');
    }
    const anchorRatio = clampNumber((cx - dimensions.left) / dimensions.chartWidth, 0, 1);

    const baseDistance = pinchState.startDistance;
    if (typeof baseDistance !== 'number' || !Number.isFinite(baseDistance) || baseDistance <= 0 || !Number.isFinite(currentDistance) || currentDistance <= 0) {
        throw new Error('Chart pinch update requires finite positive distances');
    }
    const zoomScale = Math.pow(currentDistance / baseDistance, PINCH_ZOOM_RESPONSE_EXPONENT);
    if (!Number.isFinite(zoomScale) || zoomScale <= 0) {
        throw new Error('Chart pinch update requires a finite positive zoom scale');
    }
    applyZoomAtRatio(chart, { level: storedStartLevel * zoomScale, anchorRatio, source: 'pinch', animate: false });

    const horizontalDelta = cx - storedLastCenterX;
    if (Math.abs(horizontalDelta) > 0.5) {
        const pixelsPerBar = chart.viewport.getPixelsPerBar();
        if (pixelsPerBar > 0) {
            chart.viewportState.pan.offset -= horizontalDelta / pixelsPerBar;
            chart.viewportState.pan.velocity = 0;
            chart.viewport.clampPanOffset();
        }
    }

    Object.assign(pinchState, {
        anchorRatio,
        startDistance: currentDistance,
        startLevel: chart.viewportState.zoom.level,
        lastCenterX: cx
    });
    chart.effects.requestRedraw();
};

const endPinchGesture = (chart: ChartInteractionScene, continuePointer: PointerRecord | null = null): void => {
    const state = requirePointerState(chart);
    state.pinch = null;
    chart.viewportState.pan.isZooming = false;
    chart.viewportState.pan.velocity = 0;

    if (continuePointer) {
        if (continuePointer.id === undefined || typeof continuePointer.type !== 'string') {
            throw new Error('Chart pinch continuation requires pointer id and type');
        }
        state.primaryId = continuePointer.id;
        handleMouseDown(chart, {
            clientX: continuePointer.clientX,
            clientY: continuePointer.clientY,
            button: 0,
            pointerType: continuePointer.type
        });
    } else {
        state.primaryId = null;
        if (!state.activePointers.size) {
            resetDragState(chart);
            hideCrosshair(chart);
        }
    }
    chart.effects.requestRedraw();
};

export { beginPinchGesture, endPinchGesture, updatePinchGesture };
