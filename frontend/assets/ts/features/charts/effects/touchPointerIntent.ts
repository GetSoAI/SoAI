/* SoAI - Charts feature touch pointer intent [frontend/assets/ts/features/charts/effects/touchPointerIntent.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PointerState } from '@features/charts/chartTypes.ts';
import { hideCrosshair } from '@features/charts/crosshair.ts';
import type { ChartInteractionScene } from '@features/charts/interaction/chartInteractionScene.ts';
import { handleMouseDown } from '@features/charts/interaction/actions.ts';
import { requirePointerState, resetDragState } from '@features/charts/interaction/state.ts';
import type { PointerRecord } from '@features/charts/types.ts';
import { measureLayoutPoint } from '@core/layout/elementGeometry.ts';

const TOUCH_AXIS_LOCK_PX = 8;

const isTouchLikePointer = (pointerType: string): boolean => pointerType === 'touch' || pointerType === 'pen';

const requireInteractionCanvas = (chart: ChartInteractionScene): HTMLCanvasElement => {
    const canvas = chart.surface.canvasLayers.interaction;
    if (!canvas) {
        throw new Error('Chart pointer capture requires an interaction canvas');
    }
    return canvas;
};

const releasePointerCapture = (chart: ChartInteractionScene, pointerId: number): void => {
    const canvas = requireInteractionCanvas(chart);
    if (!canvas.hasPointerCapture(pointerId)) {
        return;
    }
    canvas.releasePointerCapture(pointerId);
};

const setPointerCapture = (chart: ChartInteractionScene, pointerId: number): void => {
    const canvas = requireInteractionCanvas(chart);
    canvas.setPointerCapture(pointerId);
};

const releaseTouchPointerToNativeScroll = (chart: ChartInteractionScene, state: PointerState, pointerId: number): void => {
    state.nativeScrollPointerIds.add(pointerId);
    state.activePointers.delete(pointerId);
    if (state.primaryId === pointerId) {
        state.primaryId = null;
        resetDragState(chart);
        hideCrosshair(chart);
    }
};

const handleTouchPointerMoveIntent = (chart: ChartInteractionScene, event: PointerEvent, record: PointerRecord): boolean => {
    const { pointerId, pointerType } = event;
    const point = measureLayoutPoint(event, chart.surface.element);
    const state = requirePointerState(chart);
    if (!isTouchLikePointer(pointerType) || state.primaryId !== pointerId) {
        return true;
    }

    const startX = Number(record['x']);
    const startY = Number(record['y']);
    if (!Number.isFinite(startX) || !Number.isFinite(startY)) {
        throw new Error('Chart touch pointer record requires finite start coordinates');
    }
    const deltaX = point.x - startX;
    const deltaY = point.y - startY;
    const absDeltaX = Math.abs(deltaX);
    const absDeltaY = Math.abs(deltaY);
    if (!chart.viewportState.pan.isDragging && !chart.interaction.yAxisDrag.active && !chart.interaction.xAxisDrag.active) {
        if (Math.max(absDeltaX, absDeltaY) < TOUCH_AXIS_LOCK_PX) {
            return false;
        }
        if (absDeltaY >= absDeltaX) {
            releaseTouchPointerToNativeScroll(chart, state, pointerId);
            return false;
        }
        event.preventDefault();
        setPointerCapture(chart, pointerId);
        handleMouseDown(chart, {
            clientX: startX,
            clientY: startY,
            button: 0,
            pointerType
        });
        return true;
    }

    event.preventDefault();
    return true;
};

export { handleTouchPointerMoveIntent, isTouchLikePointer, releasePointerCapture, setPointerCapture };
