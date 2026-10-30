/* SoAI - Automation range title visibility [frontend/assets/ts/pages/automation/controllers/AutomationRangeTitleController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { optionalAutomationPeriodHeading, queryAutomationCalendarPeriods } from '@pages/automation/dom.ts';
import type { AutomationViewMode } from '@pages/automation/types.ts';

interface AutomationRangeTitleControllerDependencies {
    calendarRoot: HTMLElement;
    rangeTitle: HTMLElement;
    getViewMode: () => AutomationViewMode;
}

class AutomationRangeTitleController {
    readonly #dependencies: AutomationRangeTitleControllerDependencies;
    #observer: IntersectionObserver | null = null;
    #heading: HTMLElement | null = null;

    constructor(dependencies: AutomationRangeTitleControllerDependencies) {
        this.#dependencies = dependencies;
    }

    syncFromDom(): void {
        const viewMode = this.#dependencies.getViewMode();
        if (viewMode === 'month') {
            this.destroy();
            this.#dependencies.rangeTitle.classList.add('u-hidden');
            return;
        }
        const period = queryAutomationCalendarPeriods(this.#dependencies.calendarRoot).find((candidate) => candidate.dataset['automationCenterPeriod'] === 'true');
        const heading = period ? optionalAutomationPeriodHeading(period) : null;
        if (heading && heading === this.#heading) return;
        this.destroy();
        this.#dependencies.rangeTitle.classList.toggle('u-hidden', viewMode !== 'week');
        if (!heading || !period) return;
        this.#heading = heading;
        this.#observer = new IntersectionObserver(
            (entries) => {
                if (this.#heading !== heading) return;
                for (const entry of entries) {
                    if (entry.target !== heading) continue;
                    const atDayStart = viewMode === 'day' && period.scrollTop === 0;
                    this.#dependencies.rangeTitle.classList.toggle('u-hidden', entry.isIntersecting || atDayStart);
                }
            },
            { root: this.#dependencies.calendarRoot }
        );
        this.#observer.observe(heading);
    }

    destroy(): void {
        this.#observer?.disconnect();
        this.#observer = null;
        this.#heading = null;
    }
}

export { AutomationRangeTitleController };
