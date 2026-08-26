/* SoAI - Charts feature effects actions [frontend/assets/ts/features/charts/effects/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { DOUBLE_TAP_CONFIG } from '@core/charts/constants.ts';
import { getRequestAnimationFrame } from '@core/environment/public.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { isNullOrUndefined } from '@core/typeGuards.ts';
import { hideCrosshair } from '@features/charts/crosshair.ts';
import type { ChartInteractionScene } from '@features/charts/interaction/chartInteractionScene.ts';
import { handleTouchPointerMoveIntent, isTouchLikePointer, releasePointerCapture, setPointerCapture } from '@features/charts/effects/touchPointerIntent.ts';
import { resolvePointerRecord } from '@features/charts/guards.ts';
import { handleDoubleClickFromCoordinates, handleMouseDown, handleMouseLeave, handleMouseMove, handleMouseUp } from '@features/charts/interaction/actions.ts';
import { beginPinchGesture, endPinchGesture, updatePinchGesture } from '@features/charts/interaction/effects.ts';
import { requirePointerState, resetDragState } from '@features/charts/interaction/state.ts';
import { applyZoomAtRatio } from '@features/charts/interaction/viewportCommands.ts';
import { createLayoutPointerEventInput, createWheelPayload, getMousePosition, normalizeWheelDelta } from '@features/charts/mappers.ts';
import type { WheelPayload } from '@features/charts/types.ts';

const WHEEL_ZOOM_DELTA_SCALE = 0.0042;
const WHEEL_ZOOM_ACCELERATION_LIMIT = 0.65;
const WHEEL_ZOOM_ACTIVATION_THRESHOLD = 0.00015;

const accumulateWheelPayload = (currentPayload: WheelPayload | null, nextPayload: WheelPayload | null): WheelPayload | null => {
    if (!nextPayload) {
        return currentPayload;
    }
    if (!currentPayload) {
        return nextPayload;
    }
    return {
        clientX: nextPayload.clientX,
        clientY: nextPayload.clientY,
        deltaX: currentPayload.deltaX + nextPayload.deltaX,
        deltaY: currentPayload.deltaY + nextPayload.deltaY,
        deltaMode: nextPayload.deltaMode,
        shiftKey: currentPayload.shiftKey || nextPayload.shiftKey,
        ctrlKey: currentPayload.ctrlKey || nextPayload.ctrlKey,
        metaKey: currentPayload.metaKey || nextPayload.metaKey
    };
};
const handlePointerDown = (chart: ChartInteractionScene, event: PointerEvent): void => {
    const state = requirePointerState(chart);
    const { pointerId, pointerType, isPrimary } = event;
    const pointerInput = createLayoutPointerEventInput(event, chart.surface.element);
    const { clientX, clientY } = pointerInput;
    state.nativeScrollPointerIds.delete(pointerId);
    state.activePointers.set(pointerId, {
        x: clientX,
        y: clientY,
        id: pointerId,
        type: pointerType,
        clientX,
        clientY
    });
    if (isNullOrUndefined(state.primaryId) || isPrimary || !state.activePointers.has(state.primaryId)) {
        state.primaryId = pointerId;
    }
    const primaryPointer = state.activePointers.get(state.primaryId);
    const primaryType = primaryPointer ? primaryPointer['type'] : undefined;
    if (!state.pinch && state.activePointers.size >= 2 && (pointerType === 'touch' || primaryType === 'touch')) {
        event.preventDefault();
        setPointerCapture(chart, pointerId);
        beginPinchGesture(chart);
    } else if (!state.pinch && state.primaryId === pointerId && !isTouchLikePointer(pointerType)) {
        setPointerCapture(chart, pointerId);
        handleMouseDown(chart, pointerInput);
    }
};
const handlePointerMove = (chart: ChartInteractionScene, event: PointerEvent): void => {
    const state = requirePointerState(chart);
    const { pointerId, pointerType, buttons } = event;
    const pointerInput = createLayoutPointerEventInput(event, chart.surface.element);
    const { clientX, clientY } = pointerInput;
    if (state.nativeScrollPointerIds.has(pointerId)) {
        return;
    }
    let record = state.activePointers.get(pointerId);
    if (record) {
        record['clientX'] = clientX;
        record['clientY'] = clientY;
    } else {
        record = {
            x: clientX,
            y: clientY,
            id: pointerId,
            type: pointerType,
            clientX,
            clientY
        };
        state.activePointers.set(pointerId, record);
    }
    if (isNullOrUndefined(state.primaryId) || pointerType === 'mouse' || !state.activePointers.has(state.primaryId)) {
        state.primaryId = pointerId;
    }
    if (state.pinch) {
        if (isTouchLikePointer(pointerType)) {
            event.preventDefault();
        }
        updatePinchGesture(chart);
        return;
    }
    if (!handleTouchPointerMoveIntent(chart, event, record)) {
        return;
    }
    if (pointerType === 'mouse' || buttons === 0 || state.primaryId === pointerId) {
        handleMouseMove(chart, pointerInput);
    }
};
const handlePointerUp = (chart: ChartInteractionScene, event: PointerEvent): void => {
    const state = requirePointerState(chart);
    const { pointerId } = event;
    const pointerInput = createLayoutPointerEventInput(event, chart.surface.element);
    const { clientX, clientY } = pointerInput;
    state.nativeScrollPointerIds.delete(pointerId);
    const record = state.activePointers.get(pointerId);
    if (!record) {
        return;
    }
    record['clientX'] = clientX;
    record['clientY'] = clientY;
    releasePointerCapture(chart, pointerId);
    if (state.pinch) {
        state.activePointers.delete(pointerId);
        const remaining = Array.from(state.activePointers.values());
        endPinchGesture(chart, remaining.length === 1 ? resolvePointerRecord(remaining[0]) : null);
        return;
    }
    const now = monotonicMs();
    const lastTap = state.lastTap;
    const isDragging = chart.viewportState.pan.isDragging || chart.interaction.yAxisDrag.active || chart.interaction.xAxisDrag.active;
    const isDoubleTap = !isDragging && lastTap && now - lastTap.time < DOUBLE_TAP_CONFIG.timeThreshold && Math.abs(clientX - lastTap.x) < DOUBLE_TAP_CONFIG.distanceThreshold && Math.abs(clientY - lastTap.y) < DOUBLE_TAP_CONFIG.distanceThreshold;
    if (isDoubleTap) {
        state.lastTap = null;
        handleDoubleClickFromCoordinates(chart, clientX, clientY, event.pointerType);
    } else if (!isDragging) {
        state.lastTap = { time: now, x: clientX, y: clientY };
    }
    state.activePointers.delete(pointerId);
    if (state.primaryId === pointerId) {
        handleMouseUp(chart, pointerInput);
        state.primaryId = null;
    }
    if (!state.activePointers.size) {
        resetDragState(chart);
    } else if (isNullOrUndefined(state.primaryId)) {
        const nextValue = state.activePointers.values().next().value;
        const continuePointer = resolvePointerRecord(nextValue);
        if (!continuePointer || typeof continuePointer.id !== 'number' || typeof continuePointer.type !== 'string') {
            throw new Error('Chart pointer continuation requires pointer id and type');
        }
        state.primaryId = continuePointer.id;
        handleMouseDown(chart, {
            clientX: continuePointer.clientX,
            clientY: continuePointer.clientY,
            button: 0,
            pointerType: continuePointer.type
        });
    }
};
const handlePointerCancel = (chart: ChartInteractionScene, event: PointerEvent): void => {
    const state = requirePointerState(chart);
    const { pointerId } = event;
    state.nativeScrollPointerIds.delete(pointerId);
    releasePointerCapture(chart, pointerId);
    if (state.pinch) {
        state.activePointers.delete(pointerId);
        const remaining = Array.from(state.activePointers.values());
        endPinchGesture(chart, remaining.length === 1 ? resolvePointerRecord(remaining[0]) : null);
    } else {
        state.activePointers.delete(pointerId);
        if (state.primaryId === pointerId) {
            state.primaryId = null;
            resetDragState(chart);
        }
    }
    chart.effects.requestRedraw();
};
const handlePointerLeave = (chart: ChartInteractionScene, event: PointerEvent): void => {
    const state = requirePointerState(chart);
    if (state.pinch) {
        return;
    }
    state.nativeScrollPointerIds.delete(event.pointerId);
    state.activePointers.delete(event.pointerId);
    if (state.primaryId === event.pointerId) {
        handleMouseLeave(chart);
    } else if (!state.activePointers.size || (state.primaryId !== null && !state.activePointers.has(state.primaryId))) {
        hideCrosshair(chart);
    }
};
const handleWheelThrottled = (chart: ChartInteractionScene, event: WheelEvent): void => {
    const element = chart.surface.element;
    if (!element) {
        throw new Error('Chart requires an element to handle wheel events');
    }
    event.preventDefault();
    chart.interaction.wheelPayload = accumulateWheelPayload(chart.interaction.wheelPayload, createWheelPayload(event, element));
    if (!chart.interaction.wheelPending) {
        chart.interaction.wheelPending = true;
        const requestAnimationFrame = getRequestAnimationFrame();
        requestAnimationFrame((): void => {
            chart.interaction.wheelPending = false;
            const payload = chart.interaction.wheelPayload;
            chart.interaction.wheelPayload = null;
            if (payload) {
                handleWheel(chart, payload);
            }
        });
    }
};
const handleWheel = (chart: ChartInteractionScene, payload: WheelPayload): void => {
    const { chartWidth, left } = chart.viewport.getChartDimensions();
    if (chartWidth <= 0) {
        return;
    }
    const normDelta = normalizeWheelDelta(chart, payload);
    if (normDelta === 0) {
        return;
    }
    chart.viewport.markManual('wheel');
    const { zoom } = chart.viewportState;
    const { options } = chart.configuration;
    const modifier = (payload.shiftKey ? 1.45 : 1) * (payload.ctrlKey || payload.metaKey ? 1.35 : 1);
    const velocity = Math.abs(normDelta);
    const accel = 1 + Math.min(WHEEL_ZOOM_ACCELERATION_LIMIT, velocity / 850);
    zoom.wheelAccumulator += normDelta * WHEEL_ZOOM_DELTA_SCALE * modifier * accel;
    if (Math.abs(zoom.wheelAccumulator) < WHEEL_ZOOM_ACTIVATION_THRESHOLD) {
        return;
    }
    const deltaApply = zoom.wheelAccumulator;
    zoom.wheelAccumulator = 0;
    const { x: xCoordinate } = getMousePosition(chart, payload);
    const anchorRatio = clampNumber((xCoordinate - left) / Math.max(1, chartWidth), 0, 1);
    applyZoomAtRatio(chart, { level: zoom.level * Math.exp(-deltaApply), anchorRatio, source: 'wheel', animate: Boolean(options['enableSmoothZoom']) });
};
export { handlePointerCancel, handlePointerDown, handlePointerLeave, handlePointerMove, handlePointerUp, handleWheel, handleWheelThrottled };
