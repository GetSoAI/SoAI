/* SoAI - Automation page automations list view [frontend/assets/ts/pages/automation/rendering/automationsListView.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { getCurrentLocale } from '@core/languageservice/service.ts';
import { renderLabelAttributes } from '@core/security/labelAttributes.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { uiAttr, uiText } from '@core/security/uiHtml.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { AUTOMATION_ACTION_DELETE_AUTOMATION, AUTOMATION_ACTION_EDIT_AUTOMATION, AUTOMATION_ACTION_PREVIEW_AUTOMATION, AUTOMATION_ACTION_REGISTRY_NEXT, AUTOMATION_ACTION_REGISTRY_PREVIOUS, AUTOMATION_ACTION_TOGGLE_AUTOMATION_ENABLED, type AutomationDefinition } from '@features/automation/public.ts';
import { formatAutomationDefinitionScheduleParts } from '@pages/automation/controllers/automationDateTimeFormatters.ts';
import { renderAutomationColorAttribute } from '@pages/automation/rendering/automationColorMarkup.ts';
import type { AutomationCalendarSettings } from '@pages/automation/types.ts';

const formatRecurrenceLabel = (recurrence: AutomationDefinition['recurrence']): string => {
    if (recurrence === 'hourly') {
        return i18n.t('automation.recurrence.hourly');
    }
    if (recurrence === 'daily') {
        return i18n.t('automation.recurrence.daily');
    }
    if (recurrence === 'weekly') {
        return i18n.t('automation.recurrence.weekly');
    }
    if (recurrence === 'monthly') {
        return i18n.t('automation.recurrence.monthly');
    }
    if (recurrence === 'yearly') {
        return i18n.t('automation.recurrence.yearly');
    }
    return i18n.t('automation.recurrence.none');
};

const renderAutomationsListView = (inputArguments: { automations: readonly AutomationDefinition[]; selectedAutomationId: string | null; runningAutomationIds: ReadonlySet<string>; calendarSettings: AutomationCalendarSettings; registryLimit: number; registryOffset: number; registryHasMore: boolean; getIconSync: (icon: IconName, options?: IconOptions) => TrustedHtml }): string => {
    const title = i18n.t('automation.pane.automations.title');
    const empty = i18n.t('automation.pane.automations.empty');
    const viewLabel = i18n.t('common.view');
    const editLabel = i18n.t('common.edit');
    const deleteLabel = i18n.t('common.delete');
    const enabledLabel = i18n.t('automation.pane.automations.enabled');
    const recurringLabel = i18n.t('automation.pane.automations.recurring');

    const rows = inputArguments.automations
        .slice()
        .sort((firstValue, secondValue) => firstValue.title.localeCompare(secondValue.title, getCurrentLocale()))
        .map((automation) => {
            const isRunning = inputArguments.runningAutomationIds.has(automation.id);
            const isSelected = automation.id === inputArguments.selectedAutomationId;
            const rowClass = `automation-automation-row${automation.enabled ? ' is-enabled' : ''}${isSelected ? ' is-selected' : ''}`;
            const scheduleParts = formatAutomationDefinitionScheduleParts(automation, inputArguments.calendarSettings);
            const meta = [formatRecurrenceLabel(automation.recurrence), ...scheduleParts].join(' • ');
            const checked = automation.enabled ? ' checked' : '';

            const idAttr = uiAttr(automation.id).html;
            const colorAttr = renderAutomationColorAttribute(automation.color);
            const deleteIcon = renderIconSlot(inputArguments.getIconSync('close', { size: 14, strokeWidth: 1.5 }));
            const editIcon = renderIconSlot(inputArguments.getIconSync('edit', { size: 14, strokeWidth: 1.5 }));
            const deleteButton = `<button type="button" class="ui-round-button ui-round-button--delete" data-action="${uiAttr(AUTOMATION_ACTION_DELETE_AUTOMATION).html}" data-automation-id="${idAttr}" ${renderLabelAttributes(deleteLabel)}>` + `${deleteIcon}` + `</button>`;
            const editButton = `<button type="button" class="ui-round-button ui-round-button--edit" data-action="${uiAttr(AUTOMATION_ACTION_EDIT_AUTOMATION).html}" data-automation-id="${idAttr}" ${renderLabelAttributes(editLabel)}>` + `${editIcon}` + `</button>`;
            const enabledText = automation.enabled ? i18n.t('common.enabled') : i18n.t('common.disabled');
            const enabledToggle = `<label class="toggle-switch automation-automation-enabled-toggle">` + `<input type="checkbox" data-action="${uiAttr(AUTOMATION_ACTION_TOGGLE_AUTOMATION_ENABLED).html}" data-automation-id="${idAttr}"${checked} aria-label="${uiAttr(enabledLabel).html}" data-tooltip="${uiAttr(enabledLabel).html}">` + `<span class="slider"></span>` + `<span class="toggle-label">${uiText(enabledText).html}</span>` + `</label>`;
            const recurrenceBadge = automation.recurrence === 'none' ? '' : `<div class="automation-automation-recurrence-label${isRunning ? ' is-running' : ''}"${isRunning ? ` data-run-status="running"` : ''} aria-label="${uiAttr(recurringLabel).html}" data-tooltip="${uiAttr(recurringLabel).html}">${uiText(recurringLabel).html}</div>`;

            const actions = `<div class="automation-automation-row-actions">` + enabledToggle + recurrenceBadge + `<div class="automation-automation-row-actions-buttons">` + editButton + deleteButton + `</div>` + `</div>`;
            const main = `<button type="button" class="automation-automation-row-hit" data-action="${uiAttr(AUTOMATION_ACTION_PREVIEW_AUTOMATION).html}" data-automation-id="${idAttr}" aria-label="${uiAttr(viewLabel).html}" data-tooltip="${uiAttr(viewLabel).html}">` + `<div class="automation-automation-row-main">` + `<div class="automation-automation-title">${uiText(automation.title).html}</div>` + `<div class="automation-automation-meta">${uiText(meta).html}</div>` + `</div>` + `</button>`;

            return `<div class="${uiAttr(rowClass).html}" data-automation-id="${idAttr}"${colorAttr}${isRunning ? ` data-run-active="true"` : ''}>` + main + actions + `</div>`;
        });

    const body = rows.length ? rows.join('') : `<div class="ui-empty-state--simple">${uiText(empty).html}</div>`;
    const hasPager = inputArguments.automations.length > 0 && (inputArguments.registryOffset > 0 || inputArguments.registryHasMore);
    const countBadge = inputArguments.automations.length === 0 ? '' : `<span class="ui-status-badge status-blue">${uiText(String(inputArguments.automations.length)).html}</span>`;
    const startIndex = inputArguments.registryOffset + 1;
    const endIndex = inputArguments.registryOffset + inputArguments.automations.length;
    const pager = hasPager
        ? (() => {
              const prevDisabled = inputArguments.registryOffset <= 0 ? ' disabled' : '';
              const nextDisabled = inputArguments.registryHasMore ? '' : ' disabled';
              const prevLabel = i18n.t('common.previous');
              const nextLabel = i18n.t('common.next');
              const prevButton = `<button type="button" class="ui-icon-button ui-variant-neutral automation-automations-page automation-automations-prev"${prevDisabled} data-action="${uiAttr(AUTOMATION_ACTION_REGISTRY_PREVIOUS).html}" aria-label="${uiAttr(prevLabel).html}" data-tooltip="${uiAttr(prevLabel).html}">${renderIconSlot(inputArguments.getIconSync('chevron-left', { size: 14, strokeWidth: 1.5 }))}</button>`;
              const nextButton = `<button type="button" class="ui-icon-button ui-variant-neutral automation-automations-page automation-automations-next"${nextDisabled} data-action="${uiAttr(AUTOMATION_ACTION_REGISTRY_NEXT).html}" aria-label="${uiAttr(nextLabel).html}" data-tooltip="${uiAttr(nextLabel).html}">${renderIconSlot(inputArguments.getIconSync('chevron-right', { size: 14, strokeWidth: 1.5 }))}</button>`;
              const summary = `<div class="automation-automations-pager-summary">${uiText(`${startIndex}-${endIndex}`).html}</div>`;
              return `<div class="automation-automations-pager" role="navigation" aria-label="${uiAttr(title).html}">${summary}<div class="automation-automations-pager-controls">${prevButton}${nextButton}</div></div>`;
          })()
        : '';
    const header = `<div class="automation-pane-section-header"><div class="automation-pane-section-header-main"><div class="automation-pane-section-title">${uiText(title).html}</div>${countBadge}</div>${pager}</div>`;
    return `<section class="automation-pane-section">${header}<div class="automation-automations-list">${body}</div></section>`;
};

export { renderAutomationsListView };
