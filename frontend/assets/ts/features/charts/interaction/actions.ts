/* SoAI - Charts feature interaction actions [frontend/assets/ts/features/charts/interaction/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction } from '@core/typeGuards.ts';
import { hideCrosshair, isOverChartArea, isOverXAxis, isOverYAxis, updateCrosshair } from '@features/charts/crosshair.ts';
import { getMousePosition } from '@features/charts/mappers.ts';
import type { PointerEventInput } from '@features/charts/types.ts';
import { resetDragState, setInteractionMode } from '@features/charts/interaction/state.ts';
import type { ChartInteractionScene } from '@features/charts/interaction/chartInteractionScene.ts';
import { timeToX } from '@features/charts/viewport/timeViewport.ts';

const X_AXIS_DRAG_ZOOM_RESPONSE = 2;
const CLICK_SLOP_PX = 4;

const handleMouseDown = (chart: ChartInteractionScene, event: PointerEventInput): void => {
    if (event.button !== undefined && event.button !== 0 && event.pointerType !== 'touch') {
        return;
    }
    const { x: xCoordinate, y: yCoordinate } = getMousePosition(chart, event);
    const { pan, scale, time } = chart.viewportState;
    const { options } = chart.configuration;
    if (isFunction(event.preventDefault)) {
        event.preventDefault();
    }

    if (isOverXAxis(chart, xCoordinate, yCoordinate)) {
        if (!options.enableXAxisZoom || !Number.isFinite(time.msPerPx)) return;
        chart.interaction.xAxisDrag = { active: true, startX: xCoordinate, startMsPerPx: time.msPerPx, anchorX: xCoordinate };
        setInteractionMode(chart, 'xAxis');
        return;
    }

    const startMin = scale.min;
    const startMax = scale.max;
    if (isOverYAxis(chart, xCoordinate, yCoordinate) && startMin !== null && startMax !== null && Number.isFinite(startMin) && Number.isFinite(startMax)) {
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

    pan.isDragging = true;
    pan.lastX = xCoordinate;
    pan.lastY = yCoordinate;
    pan.travelPx = 0;
    setInteractionMode(chart, 'pan');
};

const handleMouseMove = (chart: ChartInteractionScene, event: PointerEventInput): void => {
    const { x: xCoordinate, y: yCoordinate } = getMousePosition(chart, event);
    const { xAxisDrag, yAxisDrag } = chart.interaction;
    const { pan, scale } = chart.viewportState;

    if (xAxisDrag.active) {
        const { chartWidth } = chart.viewport.getChartDimensions();
        chart.viewport.zoomTo(xAxisDrag.anchorX, xAxisDrag.startMsPerPx / Math.exp(((xCoordinate - xAxisDrag.startX) * X_AXIS_DRAG_ZOOM_RESPONSE) / Math.max(1, chartWidth)));
    } else if (yAxisDrag.active) {
        if (Math.abs(yCoordinate - yAxisDrag.startY) < 3) return;
        if (scale.auto) chart.viewport.setAutoScale(false);
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
        chart.interaction.pointer.hoverX = xCoordinate;
        chart.viewport.panByPixels(deltaX);
        if (Math.abs(deltaY) > 0.25) chart.viewport.panVertical(deltaY);
        pan.travelPx += Math.abs(deltaX) + Math.abs(deltaY);
        pan.lastX = xCoordinate;
        pan.lastY = yCoordinate;
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
    const { pan } = chart.viewportState;
    if (pan.isDragging && pan.travelPx < CLICK_SLOP_PX) retryFailedHistoryAt(chart, getMousePosition(chart, event).x);
    resetDragState(chart);
    chart.effects.requestRedraw();
};

const retryFailedHistoryAt = (chart: ChartInteractionScene, xCoordinate: number): void => {
    const history = chart.configuration.options.history;
    const oldestTs = chart.data.timestamps[0];
    const geometry = chart.geometry.renderGeometry();
    if (history?.status !== 'failed' || chart.data.dataLength === 0 || oldestTs === undefined || !geometry) return;
    if (xCoordinate >= geometry.plotLeft && xCoordinate < timeToX(geometry, oldestTs)) history.retry();
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
        chart.viewport.resetZoom();
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
