/* SoAI - Shared layout responsive manager [frontend/assets/ts/core/layout/header/ResponsiveManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { INTERFACE_SCALE_CHANGED_EVENT } from '@core/layout/interfaceScale.ts';
import { dom } from '@core/dom/dom.ts';
import { getLayoutRuntimeManager } from '@core/runtime/LayoutManager.ts';
import { ensureError } from '@core/errors/coerce.ts';

interface LayoutFrameManager {
    queue: (callback: () => void) => void;
}

export interface ResponsiveManagerHost {
    getDom: (key: string) => HTMLElement | null;
    on: (target: EventTarget, event: string, handler: (event: Event) => void) => (() => void) | void;
    getLayoutFrameManager: () => LayoutFrameManager | null;
    refreshDisplayedTitle: () => void;
}

interface ResponsiveManagerOptions {
    header: ResponsiveManagerHost;
}

export class ResponsiveManager {
    header: ResponsiveManagerHost;
    resizeObserver: ResizeObserver | null = null;
    boundUpdate: (() => void) | null = null;
    #disposers: Array<() => void> = [];
    #destroyed: boolean = false;

    constructor({ header }: ResponsiveManagerOptions) {
        this.header = header;
        this.resizeObserver = null;
        this.boundUpdate = null;
        this.#disposers = [];
        this.#destroyed = false;
    }

    #addDisposer(disposer: (() => void) | void): void {
        if (typeof disposer === 'function') {
            this.#disposers.push(disposer);
        }
    }

    async initialize(): Promise<void> {
        const headerNode = this.header.getDom('header');
        this.boundUpdate = () => this.queueUpdate();
        this.#addDisposer(this.header.on(globalThis, 'resize', this.boundUpdate));
        this.#addDisposer(this.header.on(globalThis, INTERFACE_SCALE_CHANGED_EVENT, this.boundUpdate));
        if (globalThis.visualViewport) {
            this.#addDisposer(this.header.on(globalThis.visualViewport, 'resize', this.boundUpdate));
        }
        this.#addDisposer(this.header.on(globalThis, 'soai:sidebar:ready', this.boundUpdate));
        this.#addDisposer(this.header.on(globalThis, 'soai:sidebar:destroyed', this.boundUpdate));
        if (headerNode) {
            this.resizeObserver = new ResizeObserver(this.boundUpdate);
            this.resizeObserver.observe(headerNode);
        }
        this.queueUpdate();
    }

    destroy(): void {
        this.#destroyed = true;
        for (const dispose of this.#disposers) {
            try {
                dispose();
            } catch (disposeError) {
                ensureError(disposeError);
            }
        }
        this.#disposers = [];
        if (this.resizeObserver) {
            try {
                this.resizeObserver.disconnect();
            } catch (disconnectError) {
                ensureError(disconnectError);
            }
        }
        this.resizeObserver = null;
        this.boundUpdate = null;
    }

    refresh(): void {
        if (this.#destroyed) {
            return;
        }
        this.queueUpdate();
    }

    queueUpdate(): void {
        if (this.#destroyed) {
            return;
        }
        const update = (): void => this.updateLayout();
        const layoutFrameManager = this.header.getLayoutFrameManager();
        if (!layoutFrameManager) {
            throw new Error('ResponsiveManager requires layoutFrameManager to be available');
        }
        layoutFrameManager.queue(update);
    }

    updateLayout(): void {
        if (this.#destroyed) {
            return;
        }
        const headerNode = this.header.getDom('header');
        if (!headerNode) {
            return;
        }

        const rect = measureLayoutBox(headerNode);
        const computed = getComputedStyle(headerNode);
        const hidden = computed.display === 'none' || computed.visibility === 'hidden' || rect.height <= 0;

        const root = getLayoutRuntimeManager().getRootElement();
        if (!root) {
            return;
        }

        if (hidden) {
            return;
        }

        const measured = rect.height;
        if (!Number.isFinite(measured) || measured <= 0) {
            return;
        }

        const rootStyle = getComputedStyle(root);
        const currentOffset = parseFloat(rootStyle.getPropertyValue('--layout-top-offset')) || 0;
        const currentHeaderHeight = parseFloat(rootStyle.getPropertyValue('--header-height')) || 0;
        const targetHeaderHeight = measured;
        const targetOffset = measured;

        if (Math.abs(currentOffset - targetOffset) <= 0.5 && Math.abs(currentHeaderHeight - targetHeaderHeight) <= 0.5) {
            this.header.refreshDisplayedTitle();
            return;
        }

        dom.setStyles(root, {
            '--header-height': `${targetHeaderHeight}px`,
            '--layout-top-offset': `${targetOffset}px`
        });

        this.header.refreshDisplayedTitle();
    }
}
