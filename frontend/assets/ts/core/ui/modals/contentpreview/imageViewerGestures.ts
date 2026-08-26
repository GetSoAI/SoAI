/* SoAI - Content preview image viewer gestures [frontend/assets/ts/core/ui/modals/contentpreview/imageViewerGestures.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox, measureLayoutPoint } from '@core/layout/elementGeometry.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { createContentPreviewImageViewerActivation } from '@core/ui/modals/contentpreview/imageViewerActivation.ts';
import type { ContentPreviewImageViewerRefs } from '@core/ui/modals/contentpreview/imageViewerDom.ts';
import { CONTENT_PREVIEW_IMAGE_MAX_SCALE, CONTENT_PREVIEW_IMAGE_MIN_SCALE } from '@core/ui/modals/contentpreview/imageViewerGeometry.ts';
import type { ContentPreviewImageViewerState } from '@core/ui/modals/contentpreview/imageViewerStateTypes.ts';

type MountArguments = Readonly<{
    refs: ContentPreviewImageViewerRefs;
    state: ContentPreviewImageViewerState;
}>;

type Point = Readonly<{ x: number; y: number }>;
type PointerPosition = Readonly<{ clientX: number; clientY: number }>;
type PointerDownState = Readonly<{ startX: number; startY: number; pointerType: string; moved: boolean }>;
type PanState = Readonly<{ pointerId: number; clientX: number; clientY: number; offsetX: number; offsetY: number }>;
type PinchState = Readonly<{ a: number; b: number; distance: number; scale: number; centerX: number; centerY: number }>;
type TapState = Readonly<{ time: number; x: number; y: number }>;

const distance = (first: Point, second: Point): number => Math.hypot(first.x - second.x, first.y - second.y);
const pointerDistance = (first: PointerPosition, second: PointerPosition): number => Math.hypot(first.clientX - second.clientX, first.clientY - second.clientY);

const localPoint = (viewport: HTMLElement, clientX: number, clientY: number): Point => {
    const rect = measureLayoutBox(viewport);
    return { x: clientX - rect.left, y: clientY - rect.top };
};

const createContentPreviewImageViewerGestures = ({ refs, state }: MountArguments): (() => void) => {
    const resources = new ResourceTracker();
    const activation = createContentPreviewImageViewerActivation({ refs, state, resources });
    const pointers = new Map<number, PointerPosition>();
    const pointerDown = new Map<number, PointerDownState>();
    let panState: PanState | null = null;
    let pinchState: PinchState | null = null;
    let lastTap: TapState | null = null;
    let tapResetTimer: number | null = null;
    let zoomTransitionTimer: number | null = null;

    const startSmoothZoom = (): void => {
        refs.stage.classList.add('is-zooming');
        if (zoomTransitionTimer !== null) {
            resources.clearTimeout(zoomTransitionTimer);
        }
        zoomTransitionTimer = resources.setTimeout(() => {
            zoomTransitionTimer = null;
            refs.stage.classList.remove('is-zooming');
        }, 140);
    };

    const stopSmoothZoom = (): void => {
        if (zoomTransitionTimer !== null) {
            resources.clearTimeout(zoomTransitionTimer);
            zoomTransitionTimer = null;
        }
        refs.stage.classList.remove('is-zooming');
    };

    const beginDirectGesture = (): void => {
        stopSmoothZoom();
        refs.stage.classList.add('is-gesturing');
    };

    const endDirectGesture = (): void => {
        refs.stage.classList.remove('is-gesturing');
    };

    const clearTap = (): void => {
        lastTap = null;
        if (tapResetTimer !== null) {
            resources.clearTimeout(tapResetTimer);
            tapResetTimer = null;
        }
    };

    const setTap = (tap: TapState | null): void => {
        lastTap = tap;
        if (tapResetTimer !== null) {
            resources.clearTimeout(tapResetTimer);
            tapResetTimer = null;
        }
        if (!tap) {
            return;
        }
        tapResetTimer = resources.setTimeout(() => {
            tapResetTimer = null;
            lastTap = null;
        }, 300);
    };

    const startPan = (pointerId: number): void => {
        const pointer = pointers.get(pointerId);
        if (!pointer) {
            return;
        }
        const transform = state.getTransform();
        panState = {
            pointerId,
            clientX: pointer.clientX,
            clientY: pointer.clientY,
            offsetX: transform.offsetX,
            offsetY: transform.offsetY
        };
        refs.viewport.classList.add('is-panning');
    };

    const startPinch = (): void => {
        if (pointers.size !== 2) {
            return;
        }
        const entries = Array.from(pointers.entries());
        const first = entries[0];
        const second = entries[1];
        if (!first || !second) {
            return;
        }
        const transform = state.getTransform();
        const firstPoint = first[1];
        const secondPoint = second[1];
        const pinchDistance = pointerDistance(firstPoint, secondPoint);
        if (!pinchDistance) {
            return;
        }
        pinchState = {
            a: first[0],
            b: second[0],
            distance: pinchDistance,
            scale: transform.scale,
            centerX: ((firstPoint.clientX + secondPoint.clientX) / 2 - transform.offsetX) / transform.scale,
            centerY: ((firstPoint.clientY + secondPoint.clientY) / 2 - transform.offsetY) / transform.scale
        };
        panState = null;
        refs.viewport.classList.remove('is-panning');
    };

    const handlePointerDown = (event: Event): void => {
        if (!(event instanceof PointerEvent) || !state.isReady()) {
            return;
        }
        if (event.pointerType !== 'touch') {
            event.preventDefault();
        }
        beginDirectGesture();
        refs.viewport.setPointerCapture(event.pointerId);
        const point = measureLayoutPoint(event, refs.viewport);
        pointers.set(event.pointerId, { clientX: point.x, clientY: point.y });
        pointerDown.set(event.pointerId, { startX: point.x, startY: point.y, pointerType: event.pointerType, moved: false });

        if (pointers.size === 1) {
            startPan(event.pointerId);
            return;
        }
        if (pointers.size === 2) {
            startPinch();
        }
    };

    const handlePointerMove = (event: Event): void => {
        if (!(event instanceof PointerEvent) || !state.isReady()) {
            return;
        }
        const point = measureLayoutPoint(event, refs.viewport);
        if (pointers.has(event.pointerId)) {
            pointers.set(event.pointerId, { clientX: point.x, clientY: point.y });
        }
        const downState = pointerDown.get(event.pointerId);
        if (downState && !downState.moved && distance({ x: downState.startX, y: downState.startY }, point) > 8) {
            pointerDown.set(event.pointerId, { ...downState, moved: true });
        }

        if (pinchState) {
            const first = pointers.get(pinchState.a);
            const second = pointers.get(pinchState.b);
            if (!first || !second) {
                return;
            }
            const pinchDistance = pointerDistance(first, second);
            if (!pinchDistance) {
                return;
            }
            activation.cancel();
            const nextScale = clampNumber(pinchState.scale * (pinchDistance / pinchState.distance), CONTENT_PREVIEW_IMAGE_MIN_SCALE, CONTENT_PREVIEW_IMAGE_MAX_SCALE);
            const center = localPoint(refs.viewport, (first.clientX + second.clientX) / 2, (first.clientY + second.clientY) / 2);
            state.applyTransform(nextScale, center.x - pinchState.centerX * nextScale, center.y - pinchState.centerY * nextScale, true);
            return;
        }

        if (panState && panState.pointerId === event.pointerId) {
            activation.cancel();
            state.applyTransform(state.getTransform().scale, panState.offsetX + (point.x - panState.clientX), panState.offsetY + (point.y - panState.clientY), true);
        }
    };

    const finishGesture = (): void => {
        if (pointers.size === 0) {
            panState = null;
            pinchState = null;
            refs.viewport.classList.remove('is-panning');
            state.scheduleMinimapHide(900);
            stopSmoothZoom();
            endDirectGesture();
            return;
        }
        if (pointers.size === 1) {
            pinchState = null;
            stopSmoothZoom();
            const onlyPointer = Array.from(pointers.keys())[0];
            if (onlyPointer !== undefined) {
                startPan(onlyPointer);
            }
        }
    };

    const handlePointerUpOrCancel = (event: Event): void => {
        if (!(event instanceof PointerEvent) || !state.isReady()) {
            return;
        }
        const downState = pointerDown.get(event.pointerId);
        pointers.delete(event.pointerId);
        pointerDown.delete(event.pointerId);
        if (refs.viewport.hasPointerCapture(event.pointerId)) {
            refs.viewport.releasePointerCapture(event.pointerId);
        }

        if (event.type === 'pointercancel') {
            finishGesture();
            return;
        }

        const wasTap = Boolean(downState && !downState.moved && downState.pointerType === 'touch' && !pinchState);
        finishGesture();
        if (!wasTap || pointers.size !== 0) {
            return;
        }

        const eventPoint = measureLayoutPoint(event, refs.viewport);
        const point = localPoint(refs.viewport, eventPoint.x, eventPoint.y);
        const previousTap = lastTap;
        const now = performance.now();
        if (previousTap && now - previousTap.time <= 300 && distance(previousTap, point) <= 12) {
            clearTap();
            activation.triggerDoubleActivation(point);
            return;
        }
        setTap({ time: now, x: point.x, y: point.y });
    };

    const handleDoubleClick = (event: Event): void => {
        if (!(event instanceof MouseEvent) || !state.isReady()) {
            return;
        }
        event.preventDefault();
        const point = measureLayoutPoint(event, refs.viewport);
        activation.triggerDoubleActivation(localPoint(refs.viewport, point.x, point.y));
    };

    const handleWheel = (event: Event): void => {
        if (!(event instanceof WheelEvent) || !state.isReady()) {
            return;
        }
        event.preventDefault();
        activation.cancel();
        const transform = state.getTransform();
        const point = measureLayoutPoint(event, refs.viewport);
        const pointer = localPoint(refs.viewport, point.x, point.y);
        const nextScale = clampNumber(transform.scale * Math.exp(-event.deltaY * 0.0016), CONTENT_PREVIEW_IMAGE_MIN_SCALE, CONTENT_PREVIEW_IMAGE_MAX_SCALE);
        if (nextScale === transform.scale) {
            return;
        }
        startSmoothZoom();
        const contentX = (pointer.x - transform.offsetX) / transform.scale;
        const contentY = (pointer.y - transform.offsetY) / transform.scale;
        state.applyTransform(nextScale, pointer.x - contentX * nextScale, pointer.y - contentY * nextScale, true);
    };

    resources.addEventListener(refs.image, 'dragstart', (event: Event) => {
        event.preventDefault();
    });
    resources.addEventListener(refs.viewport, 'wheel', handleWheel, { passive: false });
    resources.addEventListener(refs.viewport, 'pointerdown', handlePointerDown);
    resources.addEventListener(refs.viewport, 'pointermove', handlePointerMove);
    resources.addEventListener(refs.viewport, 'pointerup', handlePointerUpOrCancel);
    resources.addEventListener(refs.viewport, 'pointercancel', handlePointerUpOrCancel);
    resources.addEventListener(refs.viewport, 'dblclick', handleDoubleClick);

    return (): void => {
        clearTap();
        stopSmoothZoom();
        endDirectGesture();
        activation.cancel();
        resources.cleanup();
    };
};

export { createContentPreviewImageViewerGestures };
