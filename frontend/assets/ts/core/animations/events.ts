/* SoAI - Shared animations events [frontend/assets/ts/core/animations/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { HeaderAnimator } from '@core/animations/state.ts';
import { isObject } from '@core/typeGuards.ts';

class PageHeaderAnimator {
    animators: Map<HTMLElement, HeaderAnimator>;
    resizeObserver: ResizeObserver | null;
    autoHideEnabled: boolean;
    autoHideListenerReady: boolean;
    resources: ResourceTracker;

    constructor() {
        this.animators = new Map();
        this.resizeObserver = null;
        this.autoHideEnabled = true;
        this.autoHideListenerReady = false;
        this.resources = new ResourceTracker();
    }

    initialize(): void {
        if (!this.resizeObserver) {
            this.resizeObserver = new ResizeObserver((entries) => {
                const processed = new Set<HeaderAnimator>();
                for (const entry of entries) {
                    const container = entry.target.parentElement;
                    if (!container) {
                        continue;
                    }
                    const animator = this.animators.get(container);
                    if (!animator || processed.has(animator)) {
                        continue;
                    }
                    processed.add(animator);
                    animator.queueHeaderHeightUpdate();
                }
            });
        }
        this.bindAutoHideListener();
        this.setAutoHideEnabled(this.resolveAutoHideEnabled());
    }

    attach(scrollContainer: HTMLElement): void {
        if (!scrollContainer || this.animators.has(scrollContainer)) {
            return;
        }

        this.initialize();
        const autoHideEnabled = this.resolveAutoHideEnabled();
        if (autoHideEnabled !== this.autoHideEnabled) {
            this.setAutoHideEnabled(autoHideEnabled);
        }

        const animator = new HeaderAnimator(scrollContainer, this.resizeObserver, this.autoHideEnabled);
        if (animator.initialize()) {
            this.animators.set(scrollContainer, animator);
        }
    }

    detach(scrollContainer: HTMLElement): void {
        const animator = this.animators.get(scrollContainer);
        if (!animator) {
            return;
        }
        animator.destroy();
        this.animators.delete(scrollContainer);
    }

    setScrollTopWithoutReaction(scrollContainer: HTMLElement, scrollTop: number): void {
        if (!Number.isFinite(scrollTop)) {
            throw new TypeError('Header scroll position must be finite');
        }
        const animator = this.animators.get(scrollContainer);
        if (!animator) {
            scrollContainer.scrollTop = Math.max(0, scrollTop);
            return;
        }
        animator.setScrollTopWithoutReaction(scrollTop);
    }

    resolveAutoHideEnabled(): boolean {
        const body = dom.getBody();
        if (!body?.classList) {
            throw new Error('Document body must expose classList');
        }
        return !body.classList.contains('header-auto-hide-disabled');
    }

    bindAutoHideListener(): void {
        if (this.autoHideListenerReady) {
            return;
        }

        const doc = dom.getDocument();
        const win = doc?.defaultView;
        if (!win?.addEventListener) {
            throw new Error('Window is unavailable for header animator');
        }

        this.resources.addEventListener(win, 'soai:header:autoHide:changed', (event: Event) => {
            if (!(event instanceof CustomEvent)) {
                this.setAutoHideEnabled(true);
                return;
            }

            const detailValue = event.detail;
            if (!isObject(detailValue)) {
                this.setAutoHideEnabled(true);
                return;
            }

            const enabledValue = detailValue['enabled'];
            const enabled = enabledValue !== false;
            this.setAutoHideEnabled(enabled);
        });
        this.autoHideListenerReady = true;
    }

    setAutoHideEnabled(enabled: boolean): void {
        const normalized = enabled !== false;
        if (this.autoHideEnabled === normalized) {
            return;
        }
        this.autoHideEnabled = normalized;
        for (const animator of this.animators.values()) {
            animator.setAutoHideEnabled(normalized);
        }
    }
}

export { PageHeaderAnimator };
