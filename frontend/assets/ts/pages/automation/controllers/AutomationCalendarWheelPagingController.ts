/* SoAI - Automation page calendar wheel paging controller [frontend/assets/ts/pages/automation/controllers/AutomationCalendarWheelPagingController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isMonthPeriod, isPeriodAtBottom, isPeriodAtTop, isWeekOrDayPeriod, resolveCenteredPeriod } from '@pages/automation/controllers/AutomationCalendarPeriodScrollDomain.ts';

type WheelPagingDecision = { direction: -1 | 1 };

interface AutomationCalendarWheelPagingControllerDependencies {
    calendarRoot: HTMLElement;
    resolveViewportHeightPx: () => number;
    isLocked: () => boolean;
    isDragging: () => boolean;
}

const WHEEL_DEBOUNCE_MS = 400;
const WHEEL_THRESHOLD_PX = 40;
const WHEEL_ACCUM_RESET_MS = 160;

class AutomationCalendarWheelPagingController {
    readonly #dependencies: AutomationCalendarWheelPagingControllerDependencies;
    #lastWheelAtMs = 0;
    #wheelAccumPx = 0;
    #wheelAccumAtMs = 0;

    constructor(dependencies: AutomationCalendarWheelPagingControllerDependencies) {
        this.#dependencies = dependencies;
    }

    handleWheel(event: WheelEvent): WheelPagingDecision | null {
        if (this.#dependencies.isLocked() || this.#dependencies.isDragging()) {
            return null;
        }

        const rawDy = event.deltaY;

        const absX = Math.abs(event.deltaX);
        const absY = Math.abs(rawDy);

        const pagingIntent = this.#resolvePagingWheelIntent({ event, absX, absY, rawDy });
        if (pagingIntent.deltaPx === 0) {
            return null;
        }

        const now = performance.now();
        event.preventDefault();

        if (now - this.#wheelAccumAtMs > WHEEL_ACCUM_RESET_MS) {
            this.#wheelAccumPx = 0;
        }
        this.#wheelAccumAtMs = now;
        this.#wheelAccumPx += pagingIntent.deltaPx;

        if (Math.abs(this.#wheelAccumPx) < WHEEL_THRESHOLD_PX) {
            return null;
        }
        if (now - this.#lastWheelAtMs < WHEEL_DEBOUNCE_MS) {
            return null;
        }
        const height = this.#dependencies.resolveViewportHeightPx();
        if (height <= 0) {
            return null;
        }
        this.#lastWheelAtMs = now;
        const direction: -1 | 1 = this.#wheelAccumPx > 0 ? 1 : -1;
        this.#wheelAccumPx = 0;
        return { direction };
    }

    #resolvePagingWheelIntent(options: { event: WheelEvent; absX: number; absY: number; rawDy: number }): { deltaPx: number } {
        if (options.event.shiftKey && options.absX < options.absY) {
            return { deltaPx: options.rawDy };
        }
        if (options.absX > options.absY) {
            return { deltaPx: 0 };
        }
        const center = resolveCenteredPeriod(this.#dependencies.calendarRoot);
        if (center && isMonthPeriod(center)) {
            return { deltaPx: options.rawDy };
        }
        const scrollTarget = this.#resolveVerticalScrollTarget(options.event.target);
        if (!scrollTarget) {
            return { deltaPx: 0 };
        }
        if (options.rawDy > 0 && isPeriodAtBottom(scrollTarget)) {
            return { deltaPx: options.rawDy };
        }
        if (options.rawDy < 0 && isPeriodAtTop(scrollTarget)) {
            return { deltaPx: options.rawDy };
        }
        return { deltaPx: 0 };
    }

    #resolveVerticalScrollTarget(target: EventTarget | null): HTMLElement | null {
        if (!(target instanceof Element)) {
            return null;
        }
        const period = target.closest('.automation-calendar-period');
        if (!(period instanceof HTMLElement)) {
            return null;
        }
        if (isWeekOrDayPeriod(period)) {
            return period;
        }
        return null;
    }
}

export { AutomationCalendarWheelPagingController };
export type { WheelPagingDecision };
