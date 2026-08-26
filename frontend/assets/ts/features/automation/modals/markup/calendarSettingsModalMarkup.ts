/* SoAI - Automation feature calendar settings modal markup [frontend/assets/ts/features/automation/modals/markup/calendarSettingsModalMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import { renderModalBody, renderModalScaffoldMarkup, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { uiHtml, uiText } from '@core/security/uiHtml.ts';
import { renderStandardDropdownSelectControl } from '@core/ui/dropdown/selectControl.ts';
import { AUTOMATION_ACTION_SAVE_CALENDAR_SETTINGS } from '@features/automation/actions.ts';
import { AUTOMATION_CALENDAR_SETTINGS_MODAL_ID } from '@features/automation/modals/constants.ts';

const renderAutomationCalendarSettingsModalMarkup = (): TrustedHtml => {
    const closeLabel = i18n.t('common.close');
    const cancelLabel = i18n.t('automation.modal.cancel');

    const calendarSettingsTitle = i18n.t('automation.calendarSettings.title');
    const calendarSettingsSave = i18n.t('automation.calendarSettings.save');
    const firstDayLabel = i18n.t('automation.calendarSettings.fields.firstDayOfWeek');
    const weekNumbersLabel = i18n.t('automation.calendarSettings.fields.weekNumbers');
    const weekNumberingLabel = i18n.t('automation.calendarSettings.fields.weekNumbering');
    const timeFormatLabel = i18n.t('automation.calendarSettings.fields.timeFormat');
    const rangeTitleFormatLabel = i18n.t('automation.calendarSettings.fields.rangeTitleFormat');
    const rangeTitleWeekdayLabel = i18n.t('automation.calendarSettings.fields.rangeTitleWeekday');
    const modalId = AUTOMATION_CALENDAR_SETTINGS_MODAL_ID;

    const titleId = modalUiId(modalId, 'title');
    const header = renderStandardModalHeader({ modalId, title: calendarSettingsTitle, description: i18n.t('common.modalDescriptions.automationCalendar'), closeLabel, titleId });
    const body = renderModalBody(uiHtml`
        <div class="form-group setting-change-surface" data-automation-calendar-field="firstDay">
            <label for="${modalUiId(modalId, 'first-day-select')}">${firstDayLabel}</label>
            ${toTrustedUiHtml(
                renderStandardDropdownSelectControl(`<select id="${modalUiId(modalId, 'first-day-select')}" class="form-input">
                <option value="auto">${uiText(i18n.t('automation.calendarSettings.options.firstDay.auto')).html}</option>
                <option value="sunday">${uiText(i18n.t('automation.calendarSettings.options.firstDay.sunday')).html}</option>
                <option value="monday">${uiText(i18n.t('automation.calendarSettings.options.firstDay.monday')).html}</option>
            </select>`)
            )}
        </div>
        <div class="form-group setting-change-surface" data-automation-calendar-field="weekNumbers">
            <label for="${modalUiId(modalId, 'week-numbers-toggle')}">${weekNumbersLabel}</label>
            <div class="toggle-switch"><input id="${modalUiId(modalId, 'week-numbers-toggle')}" type="checkbox"><label class="slider" for="${modalUiId(modalId, 'week-numbers-toggle')}"></label></div>
        </div>
        <div class="form-group setting-change-surface" data-automation-calendar-field="weekNumbering">
            <label for="${modalUiId(modalId, 'week-numbering-select')}">${weekNumberingLabel}</label>
            ${toTrustedUiHtml(
                renderStandardDropdownSelectControl(`<select id="${modalUiId(modalId, 'week-numbering-select')}" class="form-input">
                <option value="iso">${uiText(i18n.t('automation.calendarSettings.options.weekNumbering.iso')).html}</option>
                <option value="local">${uiText(i18n.t('automation.calendarSettings.options.weekNumbering.local')).html}</option>
            </select>`)
            )}
        </div>
        <div class="form-group setting-change-surface" data-automation-calendar-field="timeFormat">
            <label for="${modalUiId(modalId, 'time-format-select')}">${timeFormatLabel}</label>
            ${toTrustedUiHtml(
                renderStandardDropdownSelectControl(`<select id="${modalUiId(modalId, 'time-format-select')}" class="form-input">
                <option value="locale">${uiText(i18n.t('automation.calendarSettings.options.timeFormat.locale')).html}</option>
                <option value="12h">${uiText(i18n.t('automation.calendarSettings.options.timeFormat.12h')).html}</option>
                <option value="24h">${uiText(i18n.t('automation.calendarSettings.options.timeFormat.24h')).html}</option>
            </select>`)
            )}
        </div>
        <div class="form-group setting-change-surface" data-automation-calendar-field="rangeTitleFormat">
            <label for="${modalUiId(modalId, 'range-title-format-select')}">${rangeTitleFormatLabel}</label>
            ${toTrustedUiHtml(
                renderStandardDropdownSelectControl(`<select id="${modalUiId(modalId, 'range-title-format-select')}" class="form-input">
                <option value="locale">${uiText(i18n.t('automation.calendarSettings.options.rangeTitleFormat.locale')).html}</option>
                <option value="iso">${uiText(i18n.t('automation.calendarSettings.options.rangeTitleFormat.iso')).html}</option>
                <option value="us">${uiText(i18n.t('automation.calendarSettings.options.rangeTitleFormat.us')).html}</option>
                <option value="eu">${uiText(i18n.t('automation.calendarSettings.options.rangeTitleFormat.eu')).html}</option>
            </select>`)
            )}
        </div>
        <div class="form-group setting-change-surface" data-automation-calendar-field="rangeTitleWeekday">
            <label for="${modalUiId(modalId, 'range-title-weekday-toggle')}">${rangeTitleWeekdayLabel}</label>
            <div class="toggle-switch"><input id="${modalUiId(modalId, 'range-title-weekday-toggle')}" type="checkbox" checked><label class="slider" for="${modalUiId(modalId, 'range-title-weekday-toggle')}"></label></div>
        </div>
        <div id="${modalUiId(modalId, 'error')}" class="error-message u-hidden"></div>
    `);
    const footer = renderSplitModalFooter({
        left: renderModalFooterCloseButton({ modalId, text: cancelLabel }),
        right: renderModalFooterActionButton({ text: calendarSettingsSave, variant: 'accent', action: AUTOMATION_ACTION_SAVE_CALENDAR_SETTINGS })
    });
    return renderModalScaffoldMarkup({ id: modalId, header, body, footer, rootAttributes: { 'data-page-scope': 'automation' } });
};

export { renderAutomationCalendarSettingsModalMarkup };
