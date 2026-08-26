/* SoAI - Automation page calendar pager controller [frontend/assets/ts/pages/automation/controllers/AutomationCalendarPagerController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';

import { isWeekOrDayPeriod, periodMaxScrollTop, resolveCenteredPeriod } from '@pages/automation/controllers/AutomationCalendarPeriodScrollDomain.ts';
import { AutomationCalendarVerticalSyncController } from '@pages/automation/controllers/AutomationCalendarVerticalSyncController.ts';
import { AutomationCalendarWheelPagingController } from '@pages/automation/controllers/AutomationCalendarWheelPagingController.ts';
import { PagerGestureRecognizerController, type PagerCommitDirection } from '@pages/automation/controllers/pager/PagerGestureRecognizerController.ts';
import { AutomationCalendarMomentumController } from '@pages/automation/controllers/pager/AutomationCalendarMomentumController.ts';
import { PagerTrackAnimatorController } from '@pages/automation/controllers/pager/PagerTrackAnimatorController.ts';
import { optionalAutomationCalendarScroll, optionalAutomationCalendarTrack } from '@pages/automation/dom.ts';

interface AutomationCalendarPagerControllerDependencies {
    calendarRoot: HTMLElement;
    requestShift: (offset: -1 | 1) => Promise<void>;
    requestAnimationFrame: (callback: () => void) => number;
    setTimeout: (callback: () => void, delay: number) => number | null;
    clearTimer: (timerId: number | null | undefined) => void;
}

class AutomationCalendarPagerController {
    readonly #dependencies: AutomationCalendarPagerControllerDependencies;
    readonly #animator: PagerTrackAnimatorController;
    readonly #gesture: PagerGestureRecognizerController;
    readonly #momentum: AutomationCalendarMomentumController;
    readonly #wheelPaging: AutomationCalendarWheelPagingController;
    readonly #verticalSync: AutomationCalendarVerticalSyncController;
    #committing = false;
    #connected = false;
    #dragScrollElement: HTMLElement | null = null;
    #dragStartScrollTop = 0;
    #dragMaxScrollTop = 0;
    readonly #onViewportWheel = (event: WheelEvent): void => {
        this.#handleWheel(event);
    };
    readonly #onViewportScrollCapture = (event: Event): void => {
        this.#onInnerScroll(event);
    };
    readonly #onAbort = (): void => {
        this.disconnect();
    };

    constructor(dependencies: AutomationCalendarPagerControllerDependencies) {
        this.#dependencies = dependencies;
        this.#animator = new PagerTrackAnimatorController({
            resolveTrack: () => this.#resolveTrack(),
            requestAnimationFrame: dependencies.requestAnimationFrame,
            setTimeout: dependencies.setTimeout,
            clearTimer: dependencies.clearTimer
        });
        this.#gesture = new PagerGestureRecognizerController({
            viewport: this.#requireViewport(),
            isLocked: () => this.#committing,
            getViewportHeightPx: () => this.#resolveViewportHeight(),
            callbacks: {
                onDragStart: (pointerType) => this.#onDragStart(pointerType),
                onDragMove: (delta) => this.#onDragMove(delta),
                onDragCancel: () => this.#animator.resetInstant(),
                onDragCommit: (direction, velocityPxMs) => this.#onGestureCommit(direction, velocityPxMs)
            }
        });
        this.#momentum = new AutomationCalendarMomentumController({
            setTimeout: dependencies.setTimeout,
            clearTimer: dependencies.clearTimer
        });
        this.#wheelPaging = new AutomationCalendarWheelPagingController({
            calendarRoot: dependencies.calendarRoot,
            resolveViewportHeightPx: () => this.#resolveViewportHeight(),
            isLocked: () => this.#committing,
            isDragging: () => this.#gesture.isDragging()
        });
        this.#verticalSync = new AutomationCalendarVerticalSyncController({
            calendarRoot: dependencies.calendarRoot,
            requestAnimationFrame: dependencies.requestAnimationFrame
        });
    }

    connect(signal: AbortSignal): void {
        if (signal.aborted || this.#connected) {
            return;
        }
        const viewport = this.#resolveViewport();
        if (!viewport) {
            return;
        }
        this.#gesture.connect(signal);
        viewport.addEventListener('wheel', this.#onViewportWheel, { signal, passive: false });
        viewport.addEventListener('scroll', this.#onViewportScrollCapture, { signal, capture: true });
        this.#connected = true;
        signal.addEventListener('abort', this.#onAbort, { once: true });
    }

    disconnect(): void {
        this.#connected = false;
        this.#committing = false;
        this.#momentum.cancel();
        this.#verticalSync.reset();
        this.#animator.disconnect();
    }

    requestCenterPeriodAfterNextRender(): void {
        if (!this.#connected) {
            return;
        }
        this.#verticalSync.requestCenterPeriodAfterNextRender();
    }

    requestCenterNowAfterNextRender(): void {
        if (!this.#connected) {
            return;
        }
        this.#verticalSync.requestCenterNowAfterNextRender();
    }

    centerNowNow(): void {
        if (!this.#connected) {
            return;
        }
        this.#verticalSync.centerNow();
    }

    cancelPendingCommit(): void {
        this.#committing = false;
        if (!this.#connected) {
            return;
        }
        this.#animator.resetInstant();
    }

    syncFromDom(): void {
        if (!this.#connected) {
            return;
        }
        this.#animator.resetInstant();
        this.#verticalSync.syncFromDom();
    }

    async animateVisiblePeriod(direction: -1 | 1): Promise<void> {
        if (!this.#connected || this.#committing || this.#gesture.isDragging()) {
            return;
        }
        const height = this.#resolveViewportHeight();
        if (height <= 0) {
            return;
        }
        this.#committing = true;
        this.#verticalSync.resetPeriodScrollTop();
        try {
            const completed = await this.#animator.animateTo(direction === 1 ? -height : height, height);
            if (completed && this.#connected) {
                await this.#dependencies.requestShift(direction);
            }
        } finally {
            this.#committing = false;
        }
    }

    #onDragStart(pointerType: string): void {
        this.#momentum.cancel();
        this.#animator.beginDrag();
        this.#dragScrollElement = null;
        this.#dragStartScrollTop = 0;
        this.#dragMaxScrollTop = 0;
        if (pointerType === 'mouse') {
            return;
        }
        const period = resolveCenteredPeriod(this.#dependencies.calendarRoot);
        if (!period || !isWeekOrDayPeriod(period)) {
            return;
        }
        const maxScrollTop = periodMaxScrollTop(period);
        if (maxScrollTop <= 0) {
            return;
        }
        this.#dragScrollElement = period;
        this.#dragStartScrollTop = period.scrollTop;
        this.#dragMaxScrollTop = maxScrollTop;
    }

    #onDragMove(deltaPx: number): number {
        const height = this.#resolveViewportHeight();
        const scrollElement = this.#dragScrollElement;
        if (!scrollElement) {
            this.#animator.updateDrag(deltaPx, height);
            return deltaPx;
        }
        const clamped = clampNumber(this.#dragStartScrollTop - deltaPx, 0, this.#dragMaxScrollTop);
        scrollElement.scrollTop = clamped;
        const paging = deltaPx - (this.#dragStartScrollTop - clamped);
        this.#animator.updateDrag(paging, height);
        return paging;
    }

    #onGestureCommit(direction: PagerCommitDirection | null, velocityPxMs: number): void {
        if (!this.#connected) {
            return;
        }
        const height = this.#resolveViewportHeight();
        if (direction === null || height <= 0) {
            if (this.#dragScrollElement) {
                this.#momentum.start(this.#dragScrollElement, -velocityPxMs);
            }
            terminateHandledPromise(this.#animator.animateTo(0, Math.max(height, 1)));
            return;
        }
        this.#committing = true;
        this.#verticalSync.resetPeriodScrollTop();
        void this.#runCommitSequence(direction, height).catch((error) => this.#handleNavigationError(error));
    }

    async #runCommitSequence(direction: PagerCommitDirection, height: number): Promise<void> {
        try {
            const completed = await this.#animator.animateTo(direction === 1 ? -height : height, height);
            if (completed && this.#connected) {
                await this.#dependencies.requestShift(direction);
            }
        } finally {
            this.#committing = false;
        }
    }

    #handleWheel(event: WheelEvent): void {
        if (!this.#connected) {
            return;
        }
        const decision = this.#wheelPaging.handleWheel(event);
        if (!decision) {
            return;
        }
        void this.animateVisiblePeriod(decision.direction).catch((error) => this.#handleNavigationError(error));
    }

    #onInnerScroll(event: Event): void {
        if (!this.#connected) {
            return;
        }
        this.#verticalSync.handleInnerScroll(event, this.#committing);
    }

    #resolveViewport(): HTMLElement | null {
        return optionalAutomationCalendarScroll(this.#dependencies.calendarRoot);
    }

    #requireViewport(): HTMLElement {
        const viewport = this.#resolveViewport();
        if (!viewport) {
            throw new Error('Automation calendar viewport missing');
        }
        return viewport;
    }

    #resolveViewportHeight(): number {
        const viewport = this.#resolveViewport();
        return viewport ? viewport.clientHeight : 0;
    }

    #resolveTrack(): HTMLElement | null {
        return optionalAutomationCalendarTrack(this.#dependencies.calendarRoot);
    }

    #handleNavigationError(error: Error): void {
        errorHandler.debug('AutomationCalendarPagerController', 'Calendar pager navigation failed', ensureError(error));
    }
}

export { AutomationCalendarPagerController };
