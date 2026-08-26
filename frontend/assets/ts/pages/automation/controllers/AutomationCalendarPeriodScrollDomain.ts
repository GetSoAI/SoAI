/* SoAI - Automation page calendar period scroll domain [frontend/assets/ts/pages/automation/controllers/AutomationCalendarPeriodScrollDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { queryAutomationCalendarPeriods } from '@pages/automation/dom.ts';

const resolveCenteredPeriod = (calendarRoot: HTMLElement): HTMLElement | null => {
    const periods = queryAutomationCalendarPeriods(calendarRoot);
    return periods.find((period) => period.dataset['automationCenterPeriod'] === 'true') ?? null;
};

const isMonthPeriod = (period: HTMLElement): boolean => period.classList.contains('automation-calendar-period--month');

const isWeekOrDayPeriod = (period: HTMLElement): boolean => period.classList.contains('automation-calendar-period--week') || period.classList.contains('automation-calendar-period--day');

const periodMaxScrollTop = (period: HTMLElement): number => Math.max(0, period.scrollHeight - period.clientHeight);

const isPeriodAtTop = (period: HTMLElement): boolean => period.scrollTop <= 0;

const isPeriodAtBottom = (period: HTMLElement): boolean => period.scrollHeight - period.clientHeight - period.scrollTop <= 1;

export { isMonthPeriod, isPeriodAtBottom, isPeriodAtTop, isWeekOrDayPeriod, periodMaxScrollTop, resolveCenteredPeriod };
