/* SoAI - Charts feature interaction actions [frontend/assets/ts/features/charts/interaction/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction } from '@core/typeGuards.ts';
import { hideCrosshair, isOverChartArea, isOverXAxis, isOverYAxis, updateCrosshair } from '@features/charts/crosshair.ts';
import { getMousePosition } from '@features/charts/mappers.ts';
import type { PointerEventInput } from '@features/charts/types.ts';
import { resetDragState, setInteractionMode } from '@features/charts/interaction/state.ts';
import { resetViewport } from '@features/charts/interaction/viewportCommands.ts';
import type { ChartInteractionScene } from '@features/charts/interaction/chartInteractionScene.ts';

const handleMouseDown = (chart: ChartInteractionScene, event: PointerEventInput): void => {
    if (event.button !== undefined && event.button !== 0 && event.pointerType !== 'touch') {
        return;
    }
    const { x: xCoordinate, y: yCoordinate } = getMousePosition(chart, event);
    const { zoom, pan, scale } = chart.viewportState;
    const { options } = chart.configuration;
    if (isOverXAxis(chart, xCoordinate, yCoordinate)) {
        return;
    }
    if (isFunction(event.preventDefault)) {
        event.preventDefault();
    }
    zoom.isAnimating = pan.isZooming = false;
    pan.targetOffset = pan.startOffset = pan.offset;
    pan.velocity = 0;

    if (isOverYAxis(chart, xCoordinate, yCoordinate) && Number.isFinite(scale.min) && Number.isFinite(scale.max)) {
        if (scale.auto || options['autoScale']) {
            chart.viewport.setAutoScale(false);
        }
        chart.viewport.markManual('y-axis-drag');
        const startMin = Number.isFinite(scale.min) ? scale.min : scale.min;
        const startMax = Number.isFinite(scale.max) ? scale.max : scale.max;
        if (startMin === null || startMax === null) {
            return;
        }
        chart.interaction.yAxisDrag = {
            active: true,
            startY: yCoordinate,
            startMin,
            startMax,
            startRange: Math.max(startMax - startMin || 0, chart.viewportState.yAxisMinRange),
            startCenter: (startMax + startMin) / 2,
            minRange: chart.viewportState.yAxisMinRange
        };
        setInteractionMode(chart, 'yAxis');
        return;
    }

    chart.viewport.markManual('pan-drag');
    pan.isDragging = true;
    pan.lastX = xCoordinate;
    pan.lastY = yCoordinate;
    setInteractionMode(chart, 'pan');
};

const handleMouseMove = (chart: ChartInteractionScene, event: PointerEventInput): void => {
    const { x: xCoordinate, y: yCoordinate } = getMousePosition(chart, event);
    const { yAxisDrag } = chart.interaction;
    const { pan, scale } = chart.viewportState;

    if (yAxisDrag.active) {
        const { chartHeight } = chart.viewport.getChartDimensions();
        const deltaY = (yAxisDrag.startY - yCoordinate) / Math.max(1, chartHeight);
        const scaleFactor = Math.exp(deltaY * 1.5);
        const range = Math.max(yAxisDrag.minRange, yAxisDrag.startRange * scaleFactor);
        const halfRange = range / 2;
        scale.min = yAxisDrag.startCenter - halfRange;
        scale.max = yAxisDrag.startCenter + halfRange;
        chart.viewport.enforceScaleBounds();
        chart.effects.requestRedraw({ static: true, data: true, interaction: true });
    } else if (pan.isDragging) {
        const deltaX = xCoordinate - pan.lastX;
        const deltaY = yCoordinate - pan.lastY;
        const ppb = chart.viewport.getPixelsPerBar();
        let hasHorizontalMovement = false;

        if (Number.isFinite(deltaX) && ppb > 0) {
            const offsetDelta = deltaX / ppb;
            if (offsetDelta !== 0) {
                pan.offset -= offsetDelta;
                pan.velocity = -offsetDelta;
                chart.viewport.clampPanOffset();
                hasHorizontalMovement = true;
            }
        } else {
            pan.velocity = 0;
        }

        const hasVerticalMovement = Math.abs(deltaY) > 0.25 ? chart.viewport.panVertical(deltaY) : false;
        pan.lastX = xCoordinate;
        pan.lastY = yCoordinate;
        if (hasHorizontalMovement || (!hasVerticalMovement && (Math.abs(deltaX) > 0 || Math.abs(deltaY) > 0))) {
            chart.effects.requestRedraw();
        }
    } else if (isOverChartArea(chart, xCoordinate, yCoordinate)) {
        updateCrosshair(chart, xCoordinate);
    } else {
        hideCrosshair(chart);
    }
};

const handleMouseUp = (chart: ChartInteractionScene, event: PointerEventInput): void => {
    if (event.pointerType === 'touch') {
        if (!isFunction(event.preventDefault)) {
            throw new Error('Chart touch pointer up requires preventDefault');
        }
        event.preventDefault();
    }
    resetDragState(chart);
    chart.effects.requestRedraw();
};

const handleMouseLeave = (chart: ChartInteractionScene): void => {
    resetDragState(chart);
    hideCrosshair(chart);
};

const handleDoubleClickFromCoordinates = (chart: ChartInteractionScene, clientX: number, clientY: number, pointerType: string | null): void => {
    const { x: xCoordinate, y: yCoordinate } = getMousePosition(chart, { clientX, clientY });
    if (isOverYAxis(chart, xCoordinate, yCoordinate)) {
        chart.viewport.setAutoScale(true);
    } else if (isOverXAxis(chart, xCoordinate, yCoordinate)) {
        resetViewport(chart, false);
    }
    if (pointerType === 'touch') {
        const canvas = chart.surface.canvasLayers.interaction;
        if (!canvas) {
            throw new Error('Chart touch double-click requires an interaction canvas');
        }
        canvas.blur();
    }
};

export { handleDoubleClickFromCoordinates, handleMouseDown, handleMouseLeave, handleMouseMove, handleMouseUp };
