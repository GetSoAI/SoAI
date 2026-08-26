/* SoAI - Shared models request distribution chart sizing [frontend/assets/ts/core/models/requestDistributionChartSizing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureElementLayoutDimensions } from '@core/layout/elementGeometry.ts';
import { getCancelAnimationFrame, getRequestAnimationFrame } from '@core/environment/public.ts';

const MOUNT_SIZE_TOLERANCE_PIXELS = 0.5;

class RequestDistributionChartSizeWatcher {
    #mount: HTMLElement | null = null;
    #observer: ResizeObserver | null = null;
    #redraw: (() => void) | null = null;
    #frameId: number | null = null;
    #renderedWidth = 0;
    #renderedHeight = 0;

    observe(mount: HTMLElement, redraw: () => void): void {
        if (this.#mount === mount && this.#observer !== null) {
            this.#redraw = redraw;
            return;
        }
        this.disconnect();
        const ResizeObserverConstructor = mount.ownerDocument.defaultView?.ResizeObserver;
        if (typeof ResizeObserverConstructor !== 'function') {
            throw new Error('Request distribution chart requires ResizeObserver');
        }
        const box = measureElementLayoutDimensions(mount);
        this.#mount = mount;
        this.#redraw = redraw;
        this.#renderedWidth = box.width;
        this.#renderedHeight = box.height;
        const observer = new ResizeObserverConstructor((): void => this.#scheduleRedraw());
        observer.observe(mount);
        this.#observer = observer;
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
        if (this.#frameId !== null) {
            return;
        }
        this.#frameId = getRequestAnimationFrame()((): void => {
            this.#frameId = null;
            this.#redrawWhenResized();
        });
    }

    #redrawWhenResized(): void {
        const mount = this.#mount;
        const redraw = this.#redraw;
        if (mount === null || redraw === null || !mount.isConnected) {
            return;
        }
        const box = measureElementLayoutDimensions(mount);
        if (Math.abs(box.width - this.#renderedWidth) < MOUNT_SIZE_TOLERANCE_PIXELS && Math.abs(box.height - this.#renderedHeight) < MOUNT_SIZE_TOLERANCE_PIXELS) {
            return;
        }
        this.#renderedWidth = box.width;
        this.#renderedHeight = box.height;
        redraw();
    }
}

export { RequestDistributionChartSizeWatcher };
