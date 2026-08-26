/* SoAI - Charts feature mapping [frontend/assets/ts/features/charts/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox, measureLayoutPoint, type GeometryBox } from '@core/layout/elementGeometry.ts';
import type { PointerEventInput, WheelPayload } from '@features/charts/types.ts';
import type { ChartInteractionScene } from '@features/charts/interaction/chartInteractionScene.ts';

const createWheelPayload = (event: WheelEvent | null, scope: Element): WheelPayload | null => {
    if (!event) {
        return null;
    }

    const point = measureLayoutPoint(event, scope);
    return {
        clientX: point.x,
        clientY: point.y,
        deltaX: event.deltaX,
        deltaY: event.deltaY,
        deltaMode: event.deltaMode,
        shiftKey: Boolean(event.shiftKey),
        ctrlKey: Boolean(event.ctrlKey),
        metaKey: Boolean(event.metaKey)
    };
};

const createLayoutPointerEventInput = (event: PointerEvent, scope: Element): PointerEventInput => {
    const point = measureLayoutPoint(event, scope);
    return { clientX: point.x, clientY: point.y, button: event.button, pointerType: event.pointerType, preventDefault: () => event.preventDefault() };
};

const getMousePosition = (
    chart: ChartInteractionScene,
    event: Pick<PointerEventInput, 'clientX' | 'clientY'>
): {
    x: number;
    y: number;
    rect: GeometryBox;
} => {
    const interactionTarget = chart.surface.element ?? chart.surface.canvasLayers.interaction;
    if (!interactionTarget) {
        return { x: 0, y: 0, rect: { x: 0, y: 0, left: 0, top: 0, right: 0, bottom: 0, width: 0, height: 0 } };
    }

    const rect = measureLayoutBox(interactionTarget);
    return { x: event.clientX - rect.left, y: event.clientY - rect.top, rect };
};

const normalizeWheelDelta = (chart: ChartInteractionScene, payload: WheelPayload): number => {
    const base = Number(payload?.deltaY) || 0;
    if (!Number.isFinite(base)) {
        return 0;
    }
    if (payload.deltaMode === 1) {
        return base * 32;
    }
    if (payload.deltaMode === 2) {
        return base * Math.max(240, measureLayoutBox(chart.surface.element ?? chart.surface.canvasLayers.interaction)?.height || 600);
    }
    return base;
};

export { createLayoutPointerEventInput, createWheelPayload, getMousePosition, normalizeWheelDelta };
