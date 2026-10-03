/* SoAI - Automation page window runs list view [frontend/assets/ts/pages/automation/rendering/windowRunsListView.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderLabelAttributes } from '@core/security/labelAttributes.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { uiAttr, uiText } from '@core/security/uiHtml.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { addDays, startOfDay } from '@core/time/localCalendar.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { AUTOMATION_ACTION_OPEN_OCCURRENCE_DETAILS, AUTOMATION_ACTION_SELECT_ZONE, AUTOMATION_ACTION_WINDOW_RUNS_BATCH_DELETE, AUTOMATION_ACTION_WINDOW_RUNS_DELETE_OCCURRENCE, AUTOMATION_ACTION_WINDOW_RUNS_ENTER_SELECT_MODE, AUTOMATION_ACTION_WINDOW_RUNS_EXIT_SELECT_MODE, AUTOMATION_ACTION_WINDOW_RUNS_TOGGLE_SELECTED, type AutomationOccurrenceResponse } from '@features/automation/public.ts';
import { buildAutomationZoneKeyForZone } from '@pages/automation/contracts/zoneKey.ts';
import { formatAutomationDate } from '@pages/automation/formatting/service.ts';
import { formatAutomationOccurrenceLabel, formatAutomationRunStatusLabel, formatAutomationRunTime, resolveAutomationRunStatusBadgeClass, resolveAutomationRunStatusContainerClass } from '@pages/automation/controllers/automationZoneFormatters.ts';
import { renderAutomationColorAttribute } from '@pages/automation/rendering/automationColorMarkup.ts';
import type { AutomationCalendarSettings } from '@pages/automation/types.ts';

interface WindowRunDayGroup {
    dayStartMs: number;
    zones: AutomationOccurrenceResponse[];
}

interface WindowRunRenderGroup {
    label: string;
    zones: AutomationOccurrenceResponse[];
}

const NEXT_RUNS_LIMIT = 10;

const resolveWindowRunDayStartMs = (utcMs: number): number => {
    return startOfDay(new Date(utcMs)).getTime();
};

const buildWindowRunDayGroups = (zones: readonly AutomationOccurrenceResponse[]): WindowRunDayGroup[] => {
    const groups: WindowRunDayGroup[] = [];
    for (const zone of zones) {
        const dayStartMs = resolveWindowRunDayStartMs(zone.scheduledAtMs);
        const previous = groups[groups.length - 1] ?? null;
        if (previous && previous.dayStartMs === dayStartMs) {
            previous.zones.push(zone);
            continue;
        }
        groups.push({ dayStartMs, zones: [zone] });
    }
    return groups;
};

const formatWindowRunDayLabel = (dayStartMs: number, todayStartMs: number, yesterdayStartMs: number, settings: AutomationCalendarSettings): string => {
    if (dayStartMs === todayStartMs) {
        return i18n.t('automation.pane.windowRuns.groups.today');
    }
    if (dayStartMs === yesterdayStartMs) {
        return i18n.t('automation.pane.windowRuns.groups.yesterday');
    }
    return formatAutomationDate(new Date(dayStartMs), settings.rangeTitleFormat, { includeYear: true, weekday: 'short' });
};

const formatWindowRunMetaDateLabel = (utcMs: number, todayStartMs: number, yesterdayStartMs: number, settings: AutomationCalendarSettings): string => {
    const dayStartMs = resolveWindowRunDayStartMs(utcMs);
    if (dayStartMs === todayStartMs) {
        return i18n.t('automation.pane.windowRuns.groups.today');
    }
    if (dayStartMs === yesterdayStartMs) {
        return i18n.t('automation.pane.windowRuns.groups.yesterday');
    }
    return formatAutomationDate(new Date(utcMs), settings.rangeTitleFormat, { includeYear: true, weekday: 'short' });
};

const buildWindowRunRenderGroups = (zones: readonly AutomationOccurrenceResponse[], options: { nowMs: number; todayStartMs: number; yesterdayStartMs: number; settings: AutomationCalendarSettings }): WindowRunRenderGroup[] => {
    const seen = new Set<string>();
    const nextRuns = zones
        .filter((zone) => zone.scheduledAtMs >= options.nowMs)
        .sort((left, right) => left.scheduledAtMs - right.scheduledAtMs)
        .slice(0, NEXT_RUNS_LIMIT);
    const groups: WindowRunRenderGroup[] = [];
    if (nextRuns.length > 0) {
        groups.push({ label: i18n.t('automation.pane.windowRuns.groups.nextRuns'), zones: nextRuns });
        for (const zone of nextRuns) {
            seen.add(buildAutomationZoneKeyForZone(zone));
        }
    }

    const todayRuns = zones.filter((zone) => resolveWindowRunDayStartMs(zone.scheduledAtMs) === options.todayStartMs && !seen.has(buildAutomationZoneKeyForZone(zone))).sort((left, right) => right.scheduledAtMs - left.scheduledAtMs);
    if (todayRuns.length > 0) {
        groups.push({ label: i18n.t('automation.pane.windowRuns.groups.today'), zones: todayRuns });
        for (const zone of todayRuns) {
            seen.add(buildAutomationZoneKeyForZone(zone));
        }
    }

    const historyZones = zones.filter((zone) => !seen.has(buildAutomationZoneKeyForZone(zone))).sort((left, right) => right.scheduledAtMs - left.scheduledAtMs);
    for (const dayGroup of buildWindowRunDayGroups(historyZones)) {
        groups.push({
            label: formatWindowRunDayLabel(dayGroup.dayStartMs, options.todayStartMs, options.yesterdayStartMs, options.settings),
            zones: dayGroup.zones
        });
    }
    return groups;
};

const renderWindowRunsListView = (inputArguments: { zones: readonly AutomationOccurrenceResponse[]; totalCount: number; selectedZoneKey: string | null; calendarSettings: AutomationCalendarSettings; selectionActive: boolean; selectedKeys: ReadonlySet<string>; getIconSync: (icon: IconName, options?: IconOptions) => TrustedHtml }): string => {
    const title = i18n.t('automation.pane.windowRuns.title');
    const empty = i18n.t('automation.pane.windowRuns.empty');
    const toolbarSelect = i18n.t('automation.pane.windowRuns.toolbar.select');
    const toolbarBatchDelete = i18n.t('automation.pane.windowRuns.toolbar.batchDelete');
    const toolbarExitSelect = i18n.t('automation.pane.windowRuns.toolbar.exitSelect');
    const detailsLabel = i18n.t('automation.pane.details.title');

    const zones = inputArguments.zones;
    const selectedCount = inputArguments.selectedKeys.size;
    const hasSelection = selectedCount > 0;
    const iconSmall: IconOptions = { size: 14, strokeWidth: 1.5 };
    const countIcon: IconOptions = { size: 12, strokeWidth: 1.5 };
    const clockCountIcon: IconOptions = { size: 12, strokeWidth: 1.7 };
    const totalRunsIcon = renderIconSlot(inputArguments.getIconSync('clock', clockCountIcon));
    const selectedRunsIcon = renderIconSlot(inputArguments.getIconSync('select', countIcon));
    const selectIcon = renderIconSlot(inputArguments.getIconSync('select', iconSmall));
    const batchDeleteIcon = renderIconSlot(inputArguments.getIconSync('delete', iconSmall));
    const exitSelectIcon = renderIconSlot(inputArguments.getIconSync('close', iconSmall));
    const totalRunsLabel = i18n.t('automation.pane.windowRuns.toolbar.totalRuns', { count: inputArguments.totalCount });
    const selectedRunsLabel = i18n.t('automation.pane.windowRuns.toolbar.selectedCount', { count: selectedCount });
    const selectButtonHidden = inputArguments.selectionActive || inputArguments.totalCount < 2;
    const toolbarMarkup =
        `<div class="automation-window-runs-toolbar batch-toolbar-container is-expanded" id="automation-window-runs-toolbar-container">` +
        `<div class="automation-window-runs-toolbar-content batch-toolbar-content">` +
        `<div class="automation-window-runs-toolbar-metrics batch-toolbar-metrics" aria-live="polite">` +
        `<span class="automation-window-runs-toolbar-count-icon batch-toolbar-count-icon automation-window-runs-total-icon${inputArguments.selectionActive ? ' u-hidden' : ''}" aria-hidden="true">${totalRunsIcon}</span>` +
        `<span class="automation-window-runs-toolbar-metric automation-window-runs-total${inputArguments.selectionActive ? ' u-hidden' : ''}">${uiText(totalRunsLabel).html}</span>` +
        `<span class="automation-window-runs-toolbar-count-icon batch-toolbar-count-icon automation-window-runs-selected-icon${inputArguments.selectionActive ? '' : ' u-hidden'}" aria-hidden="true">${selectedRunsIcon}</span>` +
        `<span class="automation-window-runs-toolbar-metric automation-window-runs-selected${inputArguments.selectionActive ? '' : ' u-hidden'}">${uiText(selectedRunsLabel).html}</span>` +
        `</div>` +
        `<div class="automation-window-runs-toolbar-actions batch-toolbar-actions">` +
        `<button type="button" class="automation-window-runs-select-btn ui-icon-button${selectButtonHidden ? ' u-hidden' : ''}" data-action="${uiAttr(AUTOMATION_ACTION_WINDOW_RUNS_ENTER_SELECT_MODE).html}" ${renderLabelAttributes(toolbarSelect)}>${selectIcon}</button>` +
        `</div>` +
        `<div class="automation-window-runs-toolbar-batch-actions batch-toolbar-batch-actions${inputArguments.selectionActive ? '' : ' u-hidden'}">` +
        `<button type="button" class="automation-window-runs-batch-delete-btn ui-icon-button ui-button ui-variant-danger${hasSelection ? '' : ' u-hidden'}" data-action="${uiAttr(AUTOMATION_ACTION_WINDOW_RUNS_BATCH_DELETE).html}" ${renderLabelAttributes(toolbarBatchDelete)}${hasSelection ? '' : ' disabled'}>${batchDeleteIcon}</button>` +
        `<button type="button" class="automation-window-runs-exit-select-btn ui-icon-button" data-action="${uiAttr(AUTOMATION_ACTION_WINDOW_RUNS_EXIT_SELECT_MODE).html}" ${renderLabelAttributes(toolbarExitSelect)}>${exitSelectIcon}</button>` +
        `</div>` +
        `</div>` +
        `</div>`;

    const nowMs = serverEpochMs();
    const todayStartMs = startOfDay(new Date(nowMs)).getTime();
    const yesterdayStartMs = addDays(new Date(todayStartMs), -1).getTime();
    const dayGroups = buildWindowRunRenderGroups(zones, { nowMs, todayStartMs, yesterdayStartMs, settings: inputArguments.calendarSettings });

    const itemsMarkup = dayGroups
        .map((dayGroup) => {
            const occurrencesLabel = i18n.t('automation.pane.windowRuns.occurrencesCount', { count: dayGroup.zones.length });
            const rows = dayGroup.zones
                .map((zone) => {
                    const key = buildAutomationZoneKeyForZone(zone);
                    const isDetailSelected = !inputArguments.selectionActive && inputArguments.selectedZoneKey === key;
                    const detailSelected = isDetailSelected ? ' is-selected' : '';
                    const batchSelected = inputArguments.selectionActive && inputArguments.selectedKeys.has(key) ? ' is-batch-selected' : '';
                    const when = formatAutomationRunTime(zone.scheduledAtMs, inputArguments.calendarSettings.timeFormat);
                    const date = formatWindowRunMetaDateLabel(zone.scheduledAtMs, todayStartMs, yesterdayStartMs, inputArguments.calendarSettings);
                    const status = formatAutomationRunStatusLabel(zone.status);
                    const badgeClass = resolveAutomationRunStatusBadgeClass(zone.status);
                    const containerClass = resolveAutomationRunStatusContainerClass(zone.status);
                    const colorAttr = renderAutomationColorAttribute(zone.color);
                    const statusBadge = `<span class="ui-status-badge ${uiAttr(badgeClass).html} automation-window-run-status-badge" data-run-status="${uiAttr(zone.status).html}">${uiText(status).html}</span>`;
                    const header = `<div class="automation-window-run-header">` + `<div dir="auto" class="automation-window-run-title">${uiText(zone.title).html}</div>` + `</div>`;
                    const deleteLabel = zone.status === 'queued' || zone.status === 'running' ? i18n.t('automation.pane.windowRuns.toolbar.stopOne') : i18n.t('automation.pane.windowRuns.toolbar.deleteOne');
                    const deleteIcon = renderIconSlot(inputArguments.getIconSync('close', { size: 14, strokeWidth: 1.5 }));
                    const detailsIcon = renderIconSlot(inputArguments.getIconSync('info', { size: 14, strokeWidth: 1.5 }));
                    const detailsButton = `<button type="button" class="ui-round-button ui-round-button--inline ui-round-button--neutral automation-window-run-details-btn" data-action="${uiAttr(AUTOMATION_ACTION_OPEN_OCCURRENCE_DETAILS).html}" data-zone-key="${uiAttr(key).html}" ${renderLabelAttributes(detailsLabel)}>${detailsIcon}</button>`;
                    const deleteButton = `<button type="button" class="ui-round-button ui-round-button--inline ui-round-button--delete automation-window-run-delete-btn" data-action="${uiAttr(AUTOMATION_ACTION_WINDOW_RUNS_DELETE_OCCURRENCE).html}" data-zone-key="${uiAttr(key).html}" ${renderLabelAttributes(deleteLabel)}>${deleteIcon}</button>`;
                    const rowButtons = inputArguments.selectionActive ? '' : deleteButton + detailsButton;
                    const actionId = inputArguments.selectionActive ? AUTOMATION_ACTION_WINDOW_RUNS_TOGGLE_SELECTED : AUTOMATION_ACTION_SELECT_ZONE;
                    const deleteClass = inputArguments.selectionActive ? '' : ' has-delete-btn';
                    const actions = `<div class="automation-window-run-row-actions">${statusBadge}<div class="automation-window-run-row-actions-buttons">${rowButtons}</div></div>`;
                    const mainInner = `<div class="automation-window-run-row-main">` + header + `<div class="automation-window-run-meta">` + `<span class="automation-window-run-date">${uiText(date).html}</span>` + `<span class="automation-window-run-time">${uiText(when).html}</span>` + `</div>` + `</div>`;
                    const itemLabel = formatAutomationOccurrenceLabel(zone, inputArguments.calendarSettings.timeFormat);
                    const pressed = inputArguments.selectionActive ? ` aria-pressed="${inputArguments.selectedKeys.has(key) ? 'true' : 'false'}"` : '';
                    const hit = `<button type="button" class="automation-window-run-item-hit" data-action="${uiAttr(actionId).html}" data-zone-key="${uiAttr(key).html}"${pressed} aria-label="${uiAttr(itemLabel).html}" data-tooltip="${uiAttr(zone.title).html}">${mainInner}</button>`;
                    return `<div class="automation-window-run-item ${uiAttr(containerClass).html}${deleteClass}${detailSelected}${batchSelected}"${colorAttr} data-zone-key="${uiAttr(key).html}" data-run-status="${uiAttr(zone.status).html}">` + hit + actions + `</div>`;
                })
                .join('');
            return `<div class="automation-window-run-group"><div class="automation-window-run-group-header">${uiText(dayGroup.label).html}<span class="ui-status-badge neutral automation-window-run-status-badge">${uiText(occurrencesLabel).html}</span></div><div class="automation-window-run-group-list">${rows}</div></div>`;
        })
        .join('');

    const header = `<div class="automation-pane-section-header"><div class="automation-pane-section-title">${uiText(title).html}</div></div>`;
    const body = zones.length === 0 ? `<div class="automation-window-runs-empty ui-empty-state--simple">${uiText(empty).html}</div>` : itemsMarkup;
    const listClass = `automation-window-runs-list${inputArguments.selectionActive ? ' selection-mode' : ''}`;
    return `<section class="automation-pane-section">${header}<div class="automation-window-runs-surface">${toolbarMarkup}<div class="${uiAttr(listClass).html}" id="automation-window-runs-list">${body}</div></div></section>`;
};

export { renderWindowRunsListView };
