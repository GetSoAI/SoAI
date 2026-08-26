/* SoAI - Automation page pager gesture recognizer controller [frontend/assets/ts/pages/automation/controllers/pager/PagerGestureRecognizerController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import { measureLayoutPoint } from '@core/layout/elementGeometry.ts';

type PagerCommitDirection = -1 | 1;

interface PagerGestureCallbacks {
    onDragStart: (pointerType: string) => void;
    onDragMove: (deltaPx: number) => number;
    onDragCancel: () => void;
    onDragCommit: (commit: PagerCommitDirection | null, velocityPxMs: number) => void;
}

interface PagerGestureRecognizerControllerDependencies {
    viewport: HTMLElement;
    isLocked: () => boolean;
    getViewportHeightPx: () => number;
    callbacks: PagerGestureCallbacks;
}

const DRAG_AXIS_LOCK_PX = 6;
const COMMIT_DISTANCE_RATIO = 0.25;
const COMMIT_VELOCITY_PX_MS = 0.4;
const VELOCITY_WINDOW_MS = 80;

class PagerGestureRecognizerController {
    readonly #dependencies: PagerGestureRecognizerControllerDependencies;
    #pointerId: number | null = null;
    #dragging = false;
    #axisLocked = false;
    #startX = 0;
    #startY = 0;
    #pagingDelta = 0;
    #velocitySamples: { t: number; y: number }[] = [];
    readonly #onPointerDown = (event: PointerEvent): void => {
        this.#handlePointerDown(event);
    };
    readonly #onPointerMove = (event: PointerEvent): void => {
        this.#handlePointerMove(event);
    };
    readonly #onPointerUp = (event: PointerEvent): void => {
        this.#handlePointerUp(event);
    };
    readonly #onPointerCancel = (event: PointerEvent): void => {
        this.#handlePointerCancel(event);
    };

    constructor(dependencies: PagerGestureRecognizerControllerDependencies) {
        this.#dependencies = dependencies;
    }

    connect(signal: AbortSignal): void {
        const viewport = this.#dependencies.viewport;
        viewport.addEventListener('pointerdown', this.#onPointerDown, { signal });
        viewport.addEventListener('pointermove', this.#onPointerMove, { signal });
        viewport.addEventListener('pointerup', this.#onPointerUp, { signal });
        viewport.addEventListener('pointercancel', this.#onPointerCancel, { signal });
    }

    isDragging(): boolean {
        return this.#dragging;
    }

    #handlePointerDown(event: PointerEvent): void {
        if (this.#dependencies.isLocked() || this.#dragging) {
            return;
        }
        if (event.pointerType === 'mouse' && event.button !== 0) {
            return;
        }
        const target = event.target;
        if (target instanceof Element && target.closest('button, a, input, textarea, select')) {
            return;
        }
        this.#pointerId = event.pointerId;
        this.#dragging = false;
        this.#axisLocked = false;
        const point = measureLayoutPoint(event, this.#dependencies.viewport);
        this.#startX = point.x;
        this.#startY = point.y;
        this.#pagingDelta = 0;
        this.#velocitySamples = [{ t: performance.now(), y: this.#startY }];
    }

    #handlePointerMove(event: PointerEvent): void {
        if (this.#pointerId !== event.pointerId) {
            return;
        }
        const point = measureLayoutPoint(event, this.#dependencies.viewport);
        const dx = point.x - this.#startX;
        const dy = point.y - this.#startY;
        if (!this.#axisLocked) {
            const absDx = Math.abs(dx);
            const absDy = Math.abs(dy);
            if (Math.max(absDx, absDy) < DRAG_AXIS_LOCK_PX) {
                return;
            }
            if (absDy <= absDx) {
                this.#abort(event);
                return;
            }
            this.#axisLocked = true;
            this.#dragging = true;
            this.#dependencies.viewport.setPointerCapture(event.pointerId);
            this.#dependencies.callbacks.onDragStart(event.pointerType);
        }
        const now = performance.now();
        this.#velocitySamples.push({ t: now, y: point.y });
        while (this.#velocitySamples.length > 1) {
            const first = this.#velocitySamples[0];
            if (first === undefined || now - first.t <= VELOCITY_WINDOW_MS) {
                break;
            }
            this.#velocitySamples.shift();
        }
        const height = this.#dependencies.getViewportHeightPx();
        const clamped = clampNumber(dy, -height, height);
        this.#pagingDelta = this.#dependencies.callbacks.onDragMove(clamped);
        event.preventDefault();
    }

    #handlePointerUp(event: PointerEvent): void {
        if (this.#pointerId !== event.pointerId) {
            return;
        }
        const wasDragging = this.#dragging;
        const paging = this.#pagingDelta;
        const velocity = this.#resolveVelocityPxPerMs();
        this.#releaseCapture(event);
        if (!wasDragging) {
            return;
        }
        const height = this.#dependencies.getViewportHeightPx();
        if (height <= 0 || paging === 0) {
            this.#dependencies.callbacks.onDragCommit(null, velocity);
            return;
        }
        const passDistance = Math.abs(paging) >= height * COMMIT_DISTANCE_RATIO;
        const velocityAgrees = velocity !== 0 && velocity < 0 === paging < 0;
        const passVelocity = velocityAgrees && Math.abs(velocity) >= COMMIT_VELOCITY_PX_MS;
        if (!passDistance && !passVelocity) {
            this.#dependencies.callbacks.onDragCommit(null, velocity);
            return;
        }
        const direction: PagerCommitDirection = paging < 0 ? 1 : -1;
        this.#dependencies.callbacks.onDragCommit(direction, velocity);
    }

    #handlePointerCancel(event: PointerEvent): void {
        if (this.#pointerId !== event.pointerId) {
            return;
        }
        const wasDragging = this.#dragging;
        this.#releaseCapture(event);
        if (wasDragging) {
            this.#dependencies.callbacks.onDragCancel();
        }
    }

    #abort(event: PointerEvent): void {
        this.#releaseCapture(event);
    }

    #releaseCapture(event: PointerEvent): void {
        const viewport = this.#dependencies.viewport;
        if (viewport.hasPointerCapture(event.pointerId)) {
            viewport.releasePointerCapture(event.pointerId);
        }
        this.#pointerId = null;
        this.#dragging = false;
        this.#axisLocked = false;
    }

    #resolveVelocityPxPerMs(): number {
        if (this.#velocitySamples.length < 2) {
            return 0;
        }
        const first = this.#velocitySamples[0];
        const last = this.#velocitySamples[this.#velocitySamples.length - 1];
        if (first === undefined || last === undefined) {
            return 0;
        }
        const dt = last.t - first.t;
        if (dt <= 0) {
            return 0;
        }
        return (last.y - first.y) / dt;
    }
}

export { PagerGestureRecognizerController };
export type { PagerCommitDirection, PagerGestureCallbacks };
