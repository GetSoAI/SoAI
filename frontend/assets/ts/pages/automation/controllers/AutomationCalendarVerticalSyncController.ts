/* SoAI - Automation page calendar vertical sync controller [frontend/assets/ts/pages/automation/controllers/AutomationCalendarVerticalSyncController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { queryAutomationCalendarPeriods, queryAutomationNowLines } from '@pages/automation/dom.ts';

type CenterMode = 'none' | 'period' | 'now';

interface AutomationCalendarVerticalSyncControllerDependencies {
    calendarRoot: HTMLElement;
    requestAnimationFrame: (callback: () => void) => number;
}

class AutomationCalendarVerticalSyncController {
    readonly #dependencies: AutomationCalendarVerticalSyncControllerDependencies;
    #scrollTop = 0;
    #centerMode: CenterMode = 'period';
    #suppressInnerScrollCapture = false;

    constructor(dependencies: AutomationCalendarVerticalSyncControllerDependencies) {
        this.#dependencies = dependencies;
    }

    reset(): void {
        this.#scrollTop = 0;
        this.#centerMode = 'none';
        this.#suppressInnerScrollCapture = false;
    }

    requestCenterPeriodAfterNextRender(): void {
        this.#centerMode = 'period';
        this.#scrollTop = 0;
    }

    requestCenterNowAfterNextRender(): void {
        this.#centerMode = 'now';
    }

    centerNow(): void {
        this.#centerMode = 'now';
        this.syncFromDom();
    }

    syncFromDom(): void {
        const periods = queryAutomationCalendarPeriods(this.#dependencies.calendarRoot);
        const center = periods.find((period) => period.dataset['automationCenterPeriod'] === 'true') ?? null;
        let targetScrollTop = this.#scrollTop;
        if (this.#centerMode === 'now' && center) {
            targetScrollTop = this.#resolveNowScrollTop(center);
            this.#scrollTop = targetScrollTop;
        }
        this.#suppressInnerScrollCapture = true;
        for (const period of periods) {
            const nextScrollTop = period === center ? targetScrollTop : 0;
            if (period.scrollHeight > period.clientHeight) {
                period.scrollTop = nextScrollTop;
            }
        }
        this.#dependencies.requestAnimationFrame(() => {
            this.#suppressInnerScrollCapture = false;
        });
        this.#centerMode = 'none';
    }

    handleInnerScroll(event: Event, isLocked: boolean): void {
        if (this.#suppressInnerScrollCapture || isLocked) {
            return;
        }
        const target = event.target;
        if (!(target instanceof HTMLElement)) {
            return;
        }
        if (!target.classList.contains('automation-calendar-period')) {
            return;
        }
        this.#scrollTop = target.scrollTop;
    }

    resetPeriodScrollTop(): void {
        this.#scrollTop = 0;
        this.#centerMode = 'period';
    }

    #resolveNowScrollTop(period: HTMLElement): number {
        const nowLines = queryAutomationNowLines(period);
        const nowLine = nowLines[0];
        if (!nowLine) {
            return 0;
        }
        const periodRect = measureLayoutBox(period);
        const lineRect = measureLayoutBox(nowLine);
        const topPx = period.scrollTop + (lineRect.top - periodRect.top);
        const centered = topPx - period.clientHeight / 2;
        const max = Math.max(0, period.scrollHeight - period.clientHeight);
        return clampNumber(centered, 0, max);
    }
}

export { AutomationCalendarVerticalSyncController };
