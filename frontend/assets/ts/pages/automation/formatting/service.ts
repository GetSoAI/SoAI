/* SoAI - Automation page formatting service [frontend/assets/ts/pages/automation/formatting/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatLocalizedDateParts } from '@core/localization/public.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { pad2, toIsoDate } from '@core/time/localCalendar.ts';
import type { AutomationWindow } from '@pages/automation/controllers/automationWindow.ts';
import type { AutomationCalendarRangeTitleFormat, AutomationCalendarSettings, AutomationCalendarTimeFormat } from '@pages/automation/types.ts';

type WeekdayFormat = 'short' | 'long';

interface AutomationHourLabel {
    primary: string;
    secondary: string | null;
}

type DateFormatOptions = {
    includeYear: boolean;
    weekday: WeekdayFormat | null;
    timeZone?: string | undefined;
};

type TimeFormatOptions = {
    timeZone?: string | undefined;
};

const buildLocaleDateTimeOptions = (base: Intl.DateTimeFormatOptions, timeZone: string | undefined): Intl.DateTimeFormatOptions => {
    if (!timeZone) {
        return { ...base };
    }
    return { ...base, timeZone };
};

const resolveIsoDateForTimeZone = (date: Date, timeZone: string | undefined): string => {
    if (!timeZone) {
        return toIsoDate(date);
    }
    const parts = new Intl.DateTimeFormat('en-US', { year: 'numeric', month: '2-digit', day: '2-digit', timeZone }).formatToParts(date);
    const year = parts.find((part) => part.type === 'year')?.value ?? '';
    const month = parts.find((part) => part.type === 'month')?.value ?? '';
    const day = parts.find((part) => part.type === 'day')?.value ?? '';
    if (!year || !month || !day) {
        throw new Error('ISO date parts missing for timeZone formatting');
    }
    return `${year}-${month}-${day}`;
};

const formatMonthShort = (date: Date, timeZone: string | undefined): string => i18n.formatDate(date, buildLocaleDateTimeOptions({ month: 'short' }, timeZone));
const formatDay2 = (date: Date, timeZone: string | undefined): string => i18n.formatDate(date, buildLocaleDateTimeOptions({ day: '2-digit' }, timeZone));
const formatYear = (date: Date, timeZone: string | undefined): string => i18n.formatDate(date, buildLocaleDateTimeOptions({ year: 'numeric' }, timeZone));
const formatWeekday = (date: Date, weekday: WeekdayFormat, timeZone: string | undefined): string => i18n.formatDate(date, buildLocaleDateTimeOptions({ weekday }, timeZone));

const formatUsDate = (date: Date, includeYear: boolean, timeZone: string | undefined): string => {
    const month = formatMonthShort(date, timeZone);
    const day = formatDay2(date, timeZone);
    if (!includeYear) {
        return `${month} ${day}`;
    }
    return `${month} ${day}, ${formatYear(date, timeZone)}`;
};

const formatEuDate = (date: Date, includeYear: boolean, timeZone: string | undefined): string => {
    const month = formatMonthShort(date, timeZone);
    const day = formatDay2(date, timeZone);
    if (!includeYear) {
        return `${day} ${month}`;
    }
    return `${day} ${month} ${formatYear(date, timeZone)}`;
};

const formatAutomationDate = (date: Date, dateFormat: AutomationCalendarRangeTitleFormat, options: DateFormatOptions): string => {
    const weekday = options.weekday;
    const includeYear = options.includeYear;
    const timeZone = options.timeZone;

    if (dateFormat === 'iso') {
        const base = resolveIsoDateForTimeZone(date, timeZone);
        if (!weekday) {
            return base;
        }
        return `${formatWeekday(date, weekday, timeZone)}, ${base}`;
    }

    if (dateFormat === 'locale') {
        const localeOptions: Intl.DateTimeFormatOptions = {
            month: 'short',
            day: '2-digit',
            ...(includeYear ? { year: 'numeric' } : {}),
            ...(weekday ? { weekday } : {})
        };
        return i18n.formatDate(date, buildLocaleDateTimeOptions(localeOptions, timeZone));
    }

    const base = dateFormat === 'us' ? formatUsDate(date, includeYear, timeZone) : formatEuDate(date, includeYear, timeZone);
    if (!weekday) {
        return base;
    }
    return `${formatWeekday(date, weekday, timeZone)}, ${base}`;
};

const formatAutomationTime = (date: Date, timeFormat: AutomationCalendarTimeFormat, options: TimeFormatOptions = {}): string => {
    const timeZone = options.timeZone;

    if (timeFormat === '12h') {
        return i18n.formatDate(date, buildLocaleDateTimeOptions({ hour: 'numeric', minute: '2-digit', hour12: true }, timeZone));
    }
    if (timeFormat === '24h') {
        return i18n.formatDate(date, buildLocaleDateTimeOptions({ hour: '2-digit', minute: '2-digit', hour12: false }, timeZone));
    }

    return i18n.formatDate(date, buildLocaleDateTimeOptions({ hour: '2-digit', minute: '2-digit' }, timeZone));
};

const toIsoYearMonth = (date: Date): string => `${date.getFullYear()}-${pad2(date.getMonth() + 1)}`;

const formatRangeTitle = (window: AutomationWindow, settings: AutomationCalendarSettings): string => {
    if (window.viewMode === 'month') {
        if (settings.rangeTitleFormat === 'iso') {
            return toIsoYearMonth(window.focusDate);
        }
        if (settings.rangeTitleFormat === 'locale') {
            return i18n.formatDate(window.focusDate, { month: 'long', year: 'numeric' });
        }
        return i18n.formatDate(window.focusDate, { month: 'long', year: 'numeric' });
    }

    if (window.viewMode === 'week') {
        if (window.weekDays.length === 0) {
            throw new Error('Automation calendar week window must provide weekDays');
        }
        const start = window.weekDays[0];
        const end = window.weekDays[window.weekDays.length - 1];
        if (!start || !end) {
            throw new Error('Automation calendar week window must provide start and end days');
        }
        const format = settings.rangeTitleFormat;
        if (format === 'iso') {
            return `${toIsoDate(start)} – ${toIsoDate(end)}`;
        }
        if (format === 'us') {
            return `${formatUsDate(start, false, undefined)} – ${formatUsDate(end, true, undefined)}`;
        }
        if (format === 'eu') {
            return `${formatEuDate(start, false, undefined)} – ${formatEuDate(end, true, undefined)}`;
        }
        return `${i18n.formatDate(start, { month: 'short', day: '2-digit' })} – ${i18n.formatDate(end, { month: 'short', day: '2-digit', year: 'numeric' })}`;
    }

    const day = window.day;
    const weekday = settings.showRangeTitleWeekday ? i18n.formatDate(day, { weekday: 'long' }) : '';
    const format = settings.rangeTitleFormat;
    if (format === 'locale') {
        return settings.showRangeTitleWeekday ? i18n.formatDate(day, { weekday: 'long', month: 'long', day: '2-digit', year: 'numeric' }) : i18n.formatDate(day, { month: 'long', day: '2-digit', year: 'numeric' });
    }
    const base = format === 'iso' ? toIsoDate(day) : format === 'us' ? formatUsDate(day, true, undefined) : formatEuDate(day, true, undefined);
    if (!weekday) {
        return base;
    }
    if (format === 'us') {
        return `${weekday}, ${base}`;
    }
    return `${weekday} · ${base}`;
};

const formatAutomationRunWhen = (utcMs: number, settings: AutomationCalendarSettings): string => {
    const date = new Date(utcMs);
    const dateLabel = formatAutomationDate(date, settings.rangeTitleFormat, { includeYear: true, weekday: 'short', timeZone: undefined });
    const timeLabel = formatAutomationTime(date, settings.timeFormat, { timeZone: undefined });
    return `${dateLabel} • ${timeLabel}`;
};

const formatAutomationWeekdayLabel = (date: Date, settings: AutomationCalendarSettings, weekday: WeekdayFormat, options: { timeZone?: string | undefined } = {}): string => {
    const timeZone = options.timeZone;
    if (settings.rangeTitleFormat === 'locale') {
        return i18n.formatDate(date, buildLocaleDateTimeOptions({ weekday }, timeZone));
    }
    return formatWeekday(date, weekday, timeZone);
};

const extractHourLabel = (parts: readonly Intl.DateTimeFormatPart[]): AutomationHourLabel => {
    const primary = parts
        .filter((part) => part.type !== 'dayPeriod')
        .map((part) => part.value)
        .join('')
        .trim();
    const dayPeriod = parts.find((part) => part.type === 'dayPeriod');
    const dayPeriodValue = toTrimmedString(dayPeriod?.value);
    return {
        primary,
        secondary: dayPeriodValue ? dayPeriodValue : null
    };
};

const buildHourLabels = (timeFormat: AutomationCalendarTimeFormat): AutomationHourLabel[] => {
    const labels: AutomationHourLabel[] = [];
    for (let hour = 0; hour < 24; hour += 1) {
        const date = new Date(2000, 0, 1, hour, 0, 0, 0);
        if (timeFormat === '12h') {
            labels.push(extractHourLabel(formatLocalizedDateParts(date, { hour: 'numeric', hour12: true })));
        } else if (timeFormat === '24h') {
            labels.push({
                primary: i18n.formatDate(date, { hour: '2-digit', minute: '2-digit', hour12: false }),
                secondary: null
            });
        } else {
            labels.push(extractHourLabel(formatLocalizedDateParts(date, { hour: 'numeric' })));
        }
    }
    return labels;
};

const resolveNowLineTopPx = (hourHeightPx: number, now: Date): number => {
    const minutes = now.getHours() * 60 + now.getMinutes() + now.getSeconds() / 60;
    return (minutes / 60) * hourHeightPx;
};

export { buildHourLabels, formatAutomationDate, formatAutomationRunWhen, formatAutomationTime, formatAutomationWeekdayLabel, formatDay2, formatRangeTitle, resolveIsoDateForTimeZone, resolveNowLineTopPx };
export type { AutomationHourLabel, WeekdayFormat };
