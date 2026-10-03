/* SoAI - Automation page zone formatters [frontend/assets/ts/pages/automation/controllers/automationZoneFormatters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { requireIsoDateToUtcMs } from '@core/time/localCalendar.ts';
import { formatAutomationFullDate, formatAutomationTime } from '@pages/automation/formatting/service.ts';
import type { AutomationOccurrenceResponse } from '@features/automation/public.ts';
import type { AutomationCalendarTimeFormat, AutomationZoneStatus } from '@pages/automation/types.ts';

type StatusBadgeClass = 'status-green' | 'status-red' | 'status-orange' | 'status-grey';
type StatusContainerClass = 'status-success' | 'status-warning' | 'status-error' | 'status-neutral';

const formatAutomationRunStatusLabel = (status: AutomationZoneStatus): string => {
    switch (status) {
        case 'scheduled':
            return i18n.t('automation.status.scheduled');
        case 'queued':
            return i18n.t('automation.status.queued');
        case 'running':
            return i18n.t('automation.status.running');
        case 'completed':
            return i18n.t('automation.status.completed');
        case 'error':
            return i18n.t('automation.status.error');
        case 'cancelled':
            return i18n.t('automation.status.cancelled');
        case 'abandoned':
            return i18n.t('automation.status.abandoned');
    }
};

const resolveAutomationRunStatusBadgeClass = (status: AutomationZoneStatus): StatusBadgeClass => {
    switch (status) {
        case 'completed':
            return 'status-green';
        case 'error':
            return 'status-red';
        case 'queued':
        case 'running':
            return 'status-orange';
        case 'scheduled':
        case 'cancelled':
        case 'abandoned':
            return 'status-grey';
    }
};

const resolveAutomationRunStatusContainerClass = (status: AutomationZoneStatus): StatusContainerClass => {
    switch (status) {
        case 'completed':
            return 'status-success';
        case 'error':
            return 'status-error';
        case 'queued':
        case 'running':
            return 'status-warning';
        case 'scheduled':
        case 'cancelled':
        case 'abandoned':
            return 'status-neutral';
    }
};

const formatAutomationRunTime = (utcMs: number, timeFormat: AutomationCalendarTimeFormat): string => {
    return formatAutomationTime(new Date(utcMs), timeFormat);
};

const formatAutomationOccurrenceLabel = (occurrence: Pick<AutomationOccurrenceResponse, 'title' | 'scheduledAtMs' | 'status'>, timeFormat: AutomationCalendarTimeFormat): string => {
    return i18n.t('automation.calendar.occurrenceLabel', { title: occurrence.title, date: formatAutomationFullDate(new Date(occurrence.scheduledAtMs)), time: formatAutomationRunTime(occurrence.scheduledAtMs, timeFormat), status: formatAutomationRunStatusLabel(occurrence.status) });
};

const formatAutomationCreateAtLabel = (isoDate: string, minutes: number, timeFormat: AutomationCalendarTimeFormat): string => {
    const date = new Date(requireIsoDateToUtcMs(isoDate, 'Automation create date'));
    const fullDate = formatAutomationFullDate(date);
    date.setHours(Math.floor(minutes / 60), minutes % 60, 0, 0);
    return i18n.t('automation.calendar.createAt', { date: fullDate, time: formatAutomationTime(date, timeFormat) });
};

const resolveAutomationRunExcerpt = (zone: AutomationOccurrenceResponse): string | null => {
    if (zone.resultExcerpt) {
        return zone.resultExcerpt;
    }
    if (zone.statusMessage) {
        return zone.statusMessage;
    }
    return null;
};

export { formatAutomationCreateAtLabel, formatAutomationOccurrenceLabel, formatAutomationRunStatusLabel, formatAutomationRunTime, resolveAutomationRunExcerpt, resolveAutomationRunStatusBadgeClass, resolveAutomationRunStatusContainerClass };
export type { StatusBadgeClass, StatusContainerClass };
