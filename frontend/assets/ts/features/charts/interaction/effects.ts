/* SoAI - Charts feature interaction effects [frontend/assets/ts/features/charts/interaction/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hideCrosshair } from '@features/charts/crosshair.ts';
import type { ChartInteractionScene } from '@features/charts/interaction/chartInteractionScene.ts';
import { getPinchMetrics, resolveFirstTwoPointers } from '@features/charts/guards.ts';
import { handleMouseDown } from '@features/charts/interaction/actions.ts';
import { requirePointerState, resetDragState } from '@features/charts/interaction/state.ts';
import { getMousePosition } from '@features/charts/mappers.ts';
import type { PointerRecord } from '@features/charts/types.ts';

const beginPinchGesture = (chart: ChartInteractionScene): void => {
    const state = requirePointerState(chart);
    if (state.activePointers.size < 2) {
        return;
    }
    const pair = resolveFirstTwoPointers(state);
    if (!pair) {
        throw new Error('Chart pinch gesture requires two valid active pointers');
    }
    const { dist, cx } = getPinchMetrics(pair[0], pair[1]);
    state.pinch = { lastDistance: dist, lastCenterX: cx };
    resetDragState(chart);
    hideCrosshair(chart);
};

const updatePinchGesture = (chart: ChartInteractionScene): void => {
    const state = requirePointerState(chart);
    const pinch = state.pinch;
    if (!pinch || state.activePointers.size < 2) {
        return;
    }
    const pair = resolveFirstTwoPointers(state);
    if (!pair) {
        throw new Error('Chart pinch update requires two valid active pointers');
    }
    const { dist, cx, cy } = getPinchMetrics(pair[0], pair[1]);
    if (Number.isFinite(dist) && dist > 0 && pinch.lastDistance > 0) chart.viewport.zoomBy(getMousePosition(chart, { clientX: cx, clientY: cy }).x, pinch.lastDistance / dist, false);
    if (Number.isFinite(cx)) chart.viewport.panByPixels(cx - pinch.lastCenterX);
    pinch.lastDistance = dist;
    pinch.lastCenterX = cx;
};

const endPinchGesture = (chart: ChartInteractionScene, continuePointer: PointerRecord | null = null): void => {
    const state = requirePointerState(chart);
    state.pinch = null;

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
