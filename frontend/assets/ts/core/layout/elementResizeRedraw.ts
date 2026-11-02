/* SoAI - Redraw scheduling for elements whose layout size changes [frontend/assets/ts/core/layout/elementResizeRedraw.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureElementLayoutDimensions, type GeometryDimensions } from '@core/layout/elementGeometry.ts';
import { getCancelAnimationFrame, getRequestAnimationFrame } from '@core/environment/public.ts';

const MOUNT_SIZE_TOLERANCE_PIXELS = 0.5;

class ElementResizeRedrawWatcher {
    readonly #measureDimensions: (element: HTMLElement) => GeometryDimensions;
    readonly #tolerancePixels: number;
    #mount: HTMLElement | null = null;
    #observer: ResizeObserver | null = null;
    #redraw: (() => void) | null = null;
    #frameId: number | null = null;
    #renderedWidth = 0;
    #renderedHeight = 0;

    constructor({ measureDimensions = measureElementLayoutDimensions, tolerancePixels = MOUNT_SIZE_TOLERANCE_PIXELS }: { measureDimensions?: (element: HTMLElement) => GeometryDimensions; tolerancePixels?: number } = {}) {
        if (!Number.isFinite(tolerancePixels) || tolerancePixels < 0) throw new Error('Element resize tolerance must be finite and non-negative');
        this.#measureDimensions = measureDimensions;
        this.#tolerancePixels = tolerancePixels;
    }

    observe(mount: HTMLElement, redraw: () => void): void {
        if (this.#mount === mount && this.#observer !== null) {
            this.#redraw = redraw;
            return;
        }
        this.disconnect();
        const ResizeObserverConstructor = mount.ownerDocument.defaultView?.ResizeObserver;
        if (typeof ResizeObserverConstructor !== 'function') {
            throw new Error('Element resize redraw requires ResizeObserver');
        }
        const box = this.#measureDimensions(mount);
        this.#mount = mount;
        this.#redraw = redraw;
        this.#renderedWidth = box.width;
        this.#renderedHeight = box.height;
        const observer = new ResizeObserverConstructor((_entries, deliveredObserver): void => {
            if (this.#observer === deliveredObserver) this.#scheduleRedraw();
        });
        this.#observer = observer;
        observer.observe(mount);
    }

    disconnect(): void {
        if (this.#frameId !== null) {
            getCancelAnimationFrame()(this.#frameId);
            this.#frameId = null;
        }
        this.#observer?.disconnect();
        this.#observer = null;
        this.#mount = null;
        this.#redraw = null;
        this.#renderedWidth = 0;
        this.#renderedHeight = 0;
    }

    #scheduleRedraw(): void {
        if (this.#frameId !== null || this.#mount === null || this.#observer === null) {
            return;
        }
        const frame = getRequestAnimationFrame()((): void => {
            if (this.#frameId !== frame) return;
            this.#frameId = null;
            this.#redrawWhenResized();
        });
        this.#frameId = frame;
    }

    #redrawWhenResized(): void {
        const mount = this.#mount;
        const redraw = this.#redraw;
        if (mount === null || redraw === null || !mount.isConnected) {
            return;
        }
        const box = this.#measureDimensions(mount);
        if ((box.width === this.#renderedWidth && box.height === this.#renderedHeight) || (Math.abs(box.width - this.#renderedWidth) < this.#tolerancePixels && Math.abs(box.height - this.#renderedHeight) < this.#tolerancePixels)) {
            return;
        }
        this.#renderedWidth = box.width;
        this.#renderedHeight = box.height;
        redraw();
    }
}

export { ElementResizeRedrawWatcher };
