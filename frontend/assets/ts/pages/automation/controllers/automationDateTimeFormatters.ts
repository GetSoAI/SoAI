/* SoAI - Automation page date time formatters [frontend/assets/ts/pages/automation/controllers/automationDateTimeFormatters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseLocalDateTimeParts, parseLocalDateTimeToUtcDate } from '@core/time/localDateTime.ts';
import { formatAutomationDate, formatAutomationTime, formatAutomationWeekdayLabel, formatDay2, resolveIsoDateForTimeZone, type WeekdayFormat } from '@pages/automation/formatting/service.ts';
import type { AutomationDefinition } from '@features/automation/public.ts';
import type { AutomationCalendarRangeTitleFormat, AutomationCalendarSettings } from '@pages/automation/types.ts';

const formatAutomationStartLocal = (startLocal: string, settings: AutomationCalendarSettings, options: { includeYear: boolean } = { includeYear: true }): string => {
    const date = parseLocalDateTimeToUtcDate(startLocal);
    if (!date) {
        return (startLocal || '').trim();
    }

    const timeZone = 'UTC';
    const dateLabel = formatAutomationDate(date, settings.rangeTitleFormat, {
        includeYear: options.includeYear || settings.rangeTitleFormat === 'iso',
        weekday: null,
        timeZone
    });
    const timeLabel = formatAutomationTime(date, settings.timeFormat, { timeZone });
    return `${dateLabel} ${timeLabel}`.trim();
};

const formatAutomationMonthDay = (date: Date, dateFormat: AutomationCalendarRangeTitleFormat, options: { timeZone?: string | undefined } = {}): string => {
    const timeZone = options.timeZone;

    if (dateFormat === 'iso') {
        const isoDate = resolveIsoDateForTimeZone(date, timeZone);
        if (isoDate.length !== 10) {
            return isoDate;
        }
        return isoDate.slice(5);
    }

    return formatAutomationDate(date, dateFormat, { includeYear: false, weekday: null, timeZone });
};

const formatAutomationWeekdayForSettings = (date: Date, settings: AutomationCalendarSettings, weekday: WeekdayFormat, options: { timeZone?: string | undefined } = {}): string => {
    return formatAutomationWeekdayLabel(date, settings, weekday, options);
};

const formatAutomationDefinitionScheduleParts = (automation: AutomationDefinition, settings: AutomationCalendarSettings): readonly string[] => {
    const recurrence = automation.recurrence;
    if (recurrence === 'none') {
        return [formatAutomationStartLocal(automation.startLocal, settings, { includeYear: true })];
    }

    const startLocalParts = parseLocalDateTimeParts(automation.startLocal);
    if (!startLocalParts) {
        return [(automation.startLocal || '').trim()];
    }
    const date = parseLocalDateTimeToUtcDate(automation.startLocal);
    if (!date) {
        return [(automation.startLocal || '').trim()];
    }

    const timeZone = 'UTC';
    const timeLabel = formatAutomationTime(date, settings.timeFormat, { timeZone });

    if (recurrence === 'hourly') {
        return [`:${String(startLocalParts.minute).padStart(2, '0')}`];
    }
    if (recurrence === 'daily') {
        return [timeLabel];
    }
    if (recurrence === 'weekly') {
        const weekdayLabel = formatAutomationWeekdayForSettings(date, settings, 'short', { timeZone });
        return [weekdayLabel, timeLabel];
    }
    if (recurrence === 'monthly') {
        const dayOfMonth = formatDay2(date, timeZone);
        return [dayOfMonth, timeLabel];
    }
    if (recurrence === 'yearly') {
        const monthDayLabel = formatAutomationMonthDay(date, settings.rangeTitleFormat, { timeZone });
        return [monthDayLabel, timeLabel];
    }

    return [timeLabel];
};

export { formatAutomationDefinitionScheduleParts, formatAutomationStartLocal };
