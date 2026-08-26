/* SoAI - Automation page zone formatters [frontend/assets/ts/pages/automation/controllers/automationZoneFormatters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatAutomationTime } from '@pages/automation/formatting/service.ts';
import type { AutomationZone } from '@features/automation/public.ts';
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

const resolveAutomationRunExcerpt = (zone: AutomationZone): string | null => {
    if (zone.resultExcerpt) {
        return zone.resultExcerpt;
    }
    if (zone.statusMessage) {
        return zone.statusMessage;
    }
    return null;
};

export { formatAutomationRunStatusLabel, formatAutomationRunTime, resolveAutomationRunExcerpt, resolveAutomationRunStatusBadgeClass, resolveAutomationRunStatusContainerClass };
export type { StatusBadgeClass, StatusContainerClass };
