/* SoAI - Content preview image viewer gestures [frontend/assets/ts/core/ui/modals/contentpreview/imageViewerGestures.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox, measureLayoutPoint } from '@core/layout/elementGeometry.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { createContentPreviewImageViewerActivation } from '@core/ui/modals/contentpreview/imageViewerActivation.ts';
import { createContentPreviewImageViewerMotion } from '@core/ui/modals/contentpreview/imageViewerMotion.ts';
import { createContentPreviewImageViewerPaging, type ImageViewerGestureActions } from '@core/ui/modals/contentpreview/imageViewerPaging.ts';
import type { ContentPreviewImageViewerRefs } from '@core/ui/modals/contentpreview/imageViewerDom.ts';
import { CONTENT_PREVIEW_IMAGE_MAX_SCALE, resolveElasticImageScale, resolveViewerOffsets, restoreImageDisplacement, type Point } from '@core/ui/modals/contentpreview/imageViewerGeometry.ts';
import type { ContentPreviewImageViewerState } from '@core/ui/modals/contentpreview/imageViewerStateTypes.ts';

type MountArguments = Readonly<{ refs: ContentPreviewImageViewerRefs; state: ContentPreviewImageViewerState; actions: ImageViewerGestureActions }>;
type TrackedPointer = Readonly<{ x: number; y: number; pointerType: string }>;
type PanState = { pointerId: number; start: Point; last: Point; offset: Point; startedAt: number; lastAt: number; velocity: Point; moved: boolean; mode: 'pending' | 'pan' | 'page' | 'dismiss' };
type PinchState = Readonly<{ firstId: number; secondId: number; distance: number; scale: number; content: Point }>;

const createContentPreviewImageViewerGestures = ({ refs, state, actions }: MountArguments) => {
    const resources = new ResourceTracker();
    const motion = createContentPreviewImageViewerMotion(refs, state, resources);
    const activation = createContentPreviewImageViewerActivation({ state, motion });
    const paging = createContentPreviewImageViewerPaging(refs, resources, actions);
    const pointers = new Map<number, TrackedPointer>();
    let pan: PanState | null = null;
    let pinch: PinchState | null = null;
    let multiTouch = false;
    let lastPinchCenter: Point | undefined;
    let wheelTarget: number | null = null;
    let lastWheelAt = -Infinity;

    const localPoint = (point: Point): Point => {
        const bounds = measureLayoutBox(refs.viewport);
        return { x: point.x - bounds.left, y: point.y - bounds.top };
    };

    const rebase = (): void => {
        pan = null;
        pinch = null;
        const entries = Array.from(pointers.entries());
        const first = entries[0];
        if (!first) {
            refs.viewport.classList.remove('is-panning');
            refs.stage.classList.remove('is-gesturing');
            return;
        }
        const transform = state.getTransform();
        const firstPoint = localPoint(first[1]);
        const second = entries[1];
        if (second) {
            multiTouch = true;
            activation.clearTap();
            paging.reset(true);
            const secondPoint = localPoint(second[1]);
            const distance = Math.hypot(firstPoint.x - secondPoint.x, firstPoint.y - secondPoint.y);
            const center = { x: (firstPoint.x + secondPoint.x) / 2, y: (firstPoint.y + secondPoint.y) / 2 };
            lastPinchCenter = center;
            pinch = { firstId: first[0], secondId: second[0], distance, scale: transform.scale, content: { x: (center.x - transform.offsetX) / transform.scale, y: (center.y - transform.offsetY) / transform.scale } };
        } else {
            const now = performance.now();
            const geometry = state.getGeometry();
            const bounded = resolveViewerOffsets(geometry.imageWidth, geometry.imageHeight, geometry.viewportWidth, geometry.viewportHeight, transform.scale, transform.offsetX, transform.offsetY);
            const offset = first[1].pointerType === 'touch' ? { x: bounded.x + restoreImageDisplacement(transform.offsetX - bounded.x, geometry.viewportWidth), y: bounded.y + restoreImageDisplacement(transform.offsetY - bounded.y, geometry.viewportHeight) } : { x: transform.offsetX, y: transform.offsetY };
            pan = { pointerId: first[0], start: firstPoint, last: firstPoint, offset, startedAt: now, lastAt: now, velocity: { x: 0, y: 0 }, moved: multiTouch, mode: multiTouch ? 'pan' : 'pending' };
        }
    };

    const clearPointers = (): void => {
        const pointerIds = Array.from(pointers.keys());
        pointers.clear();
        pan = null;
        pinch = null;
        multiTouch = false;
        for (const pointerId of pointerIds) {
            if (refs.viewport.hasPointerCapture(pointerId)) {
                refs.viewport.releasePointerCapture(pointerId);
            }
        }
        refs.viewport.classList.remove('is-panning');
        refs.stage.classList.remove('is-gesturing');
    };

    const cancelGesture = (): void => {
        clearPointers();
        activation.clearTap();
        wheelTarget = null;
        motion.cancel();
        paging.reset(true);
        const transform = state.getTransform();
        state.applyTransform(transform.scale, transform.offsetX, transform.offsetY, false);
    };

    const handlePointerDown = (event: Event): void => {
        if (!(event instanceof PointerEvent) || !state.isReady() || actions.isBlocked() || (event.pointerType !== 'touch' && event.button !== 0)) {
            return;
        }
        if (event.pointerType !== 'touch') {
            event.preventDefault();
        }
        motion.cancel();
        paging.reset(true);
        wheelTarget = null;
        refs.stage.classList.add('is-gesturing');
        refs.viewport.setPointerCapture(event.pointerId);
        pointers.set(event.pointerId, { ...measureLayoutPoint(event, refs.viewport), pointerType: event.pointerType });
        if (pointers.size <= 2) {
            rebase();
        }
    };

    const handlePointerMove = (event: Event): void => {
        if (!(event instanceof PointerEvent) || !pointers.has(event.pointerId) || !state.isReady()) {
            return;
        }
        const position = measureLayoutPoint(event, refs.viewport);
        pointers.set(event.pointerId, { ...position, pointerType: event.pointerType });
        const point = localPoint(position);
        if (pinch) {
            const first = pointers.get(pinch.firstId);
            const second = pointers.get(pinch.secondId);
            if (!first || !second) {
                return;
            }
            if (pinch.distance === 0) {
                rebase();
                return;
            }
            const center = localPoint({ x: (first.x + second.x) / 2, y: (first.y + second.y) / 2 });
            lastPinchCenter = center;
            const geometry = state.getGeometry();
            const scale = resolveElasticImageScale((pinch.scale * Math.hypot(first.x - second.x, first.y - second.y)) / pinch.distance, geometry.fitScale);
            const offsets = resolveViewerOffsets(geometry.imageWidth, geometry.imageHeight, geometry.viewportWidth, geometry.viewportHeight, scale, center.x - pinch.content.x * scale, center.y - pinch.content.y * scale);
            state.applyTransform(scale, offsets.x, offsets.y, true, true);
            return;
        }
        if (!pan || pan.pointerId !== event.pointerId) {
            return;
        }
        const delta = { x: point.x - pan.start.x, y: point.y - pan.start.y };
        const now = performance.now();
        const elapsed = Math.max(1, now - pan.lastAt);
        const retention = Math.pow(0.6, elapsed / 16.67);
        pan.velocity = { x: pan.velocity.x * retention + ((point.x - pan.last.x) / elapsed) * (1 - retention), y: pan.velocity.y * retention + ((point.y - pan.last.y) / elapsed) * (1 - retention) };
        pan.last = point;
        pan.lastAt = now;
        if (!pan.moved && Math.hypot(delta.x, delta.y) <= 8) {
            return;
        }
        pan.moved = true;
        activation.clearTap();
        if (pan.mode === 'pending') {
            const atFit = state.getTransform().scale <= state.getGeometry().fitScale * 1.001;
            pan.mode = event.pointerType === 'touch' && atFit && !multiTouch ? (Math.abs(delta.x) >= Math.abs(delta.y) ? 'page' : 'dismiss') : 'pan';
        }
        if (pan.mode === 'page' || pan.mode === 'dismiss') {
            paging.drag(pan.mode, delta);
        } else {
            if (multiTouch) {
                lastPinchCenter = point;
            }
            refs.viewport.classList.add('is-panning');
            motion.pan(pan.offset.x + delta.x, pan.offset.y + delta.y, event.pointerType === 'touch');
        }
    };

    const handlePointerEnd = (event: Event): void => {
        if (!(event instanceof PointerEvent) || !pointers.has(event.pointerId)) {
            return;
        }
        if (event.type !== 'pointerup') {
            cancelGesture();
            return;
        }
        const completed = pan;
        const wasPinch = pinch !== null;
        const pinchPointerEnded = pinch && (pinch.firstId === event.pointerId || pinch.secondId === event.pointerId);
        pointers.delete(event.pointerId);
        if (refs.viewport.hasPointerCapture(event.pointerId)) {
            refs.viewport.releasePointerCapture(event.pointerId);
        }
        if (pointers.size > 0) {
            if (pinchPointerEnded || completed?.pointerId === event.pointerId) {
                rebase();
            }
            return;
        }
        const wasMultiTouch = multiTouch;
        clearPointers();
        state.scheduleMinimapHide(900);
        if (wasPinch || wasMultiTouch) {
            motion.settle(lastPinchCenter);
        } else if (completed?.moved) {
            const delta = { x: completed.last.x - completed.start.x, y: completed.last.y - completed.start.y };
            if (completed.mode === 'page' || completed.mode === 'dismiss') {
                paging.finish(completed.mode, delta, performance.now() - completed.startedAt);
            } else if (event.pointerType === 'touch') {
                motion.inertia(performance.now() - completed.lastAt > 80 ? { x: 0, y: 0 } : completed.velocity);
            }
        } else {
            motion.settle();
            if (event.pointerType === 'touch') {
                activation.tap(localPoint(measureLayoutPoint(event, refs.viewport)));
            }
        }
    };

    const handleWheel = (event: Event): void => {
        if (!(event instanceof WheelEvent) || !state.isReady() || actions.isBlocked() || pointers.size > 0) {
            return;
        }
        event.preventDefault();
        motion.cancel();
        activation.clearTap();
        paging.reset(true);
        const geometry = state.getGeometry();
        const now = performance.now();
        const currentScale = wheelTarget !== null && now - lastWheelAt < 160 ? wheelTarget : state.getTransform().scale;
        const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? geometry.viewportHeight : 1);
        const nextScale = clampNumber(currentScale * Math.exp(-delta * 0.0016), geometry.fitScale, CONTENT_PREVIEW_IMAGE_MAX_SCALE);
        lastWheelAt = now;
        wheelTarget = nextScale;
        if (nextScale !== state.getTransform().scale) {
            motion.zoomAt(nextScale, localPoint(measureLayoutPoint(event, refs.viewport)), 140);
        }
    };

    resources.addEventListener(refs.image, 'dragstart', (event: Event) => event.preventDefault());
    resources.addEventListener(refs.viewport, 'wheel', handleWheel, { passive: false });
    resources.addEventListener(refs.viewport, 'pointerdown', handlePointerDown);
    resources.addEventListener(refs.viewport, 'pointermove', handlePointerMove);
    resources.addEventListener(refs.viewport, 'pointerup', handlePointerEnd);
    resources.addEventListener(refs.viewport, 'pointercancel', handlePointerEnd);
    resources.addEventListener(refs.viewport, 'lostpointercapture', handlePointerEnd);
    resources.addEventListener(refs.viewport, 'dblclick', (event: Event) => {
        if (event instanceof MouseEvent && state.isReady() && !actions.isBlocked() && pointers.size === 0) {
            event.preventDefault();
            wheelTarget = null;
            activation.doubleClick(localPoint(measureLayoutPoint(event, refs.viewport)));
        }
    });
    resources.addEventListener(refs.viewer.ownerDocument, 'visibilitychange', () => {
        if (refs.viewer.ownerDocument.hidden && !actions.isBlocked()) {
            cancelGesture();
        }
    });
    resources.track(
        state.subscribeResize(() => {
            motion.cancel();
            if (!actions.isBlocked()) {
                paging.reset(true);
            }
            wheelTarget = null;
            multiTouch = pointers.size > 0;
            activation.clearTap();
            rebase();
        })
    );

    const suspend = (): void => {
        clearPointers();
        activation.clearTap();
        wheelTarget = null;
        motion.cancel();
        paging.cancel();
    };

    return Object.freeze({
        suspend,
        cancel: (): void => {
            suspend();
            motion.settle();
            paging.reset();
        },
        dispose: (): void => {
            suspend();
            paging.reset(true);
            resources.cleanup();
        }
    });
};

export { createContentPreviewImageViewerGestures };
