/* SoAI - Automation page calendar settings modal controller [frontend/assets/ts/pages/automation/controllers/AutomationCalendarSettingsModalController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAutomationCalendarFirstDay, isAutomationCalendarRangeTitleFormat, isAutomationCalendarTimeFormat, isAutomationCalendarWeekNumbering } from '@core/automation/guards.ts';
import { readTrimmedSelectValue } from '@core/dom/formValues.ts';
import { narrowInput, narrowSelect } from '@core/dom/narrowElement.ts';
import { setSelectValueAndSyncDefault } from '@core/dom/selectSelection.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { clearStatusSurface, setStatusSurface } from '@core/ui/statusSurface.ts';
import { AUTOMATION_CALENDAR_SETTINGS_MODAL_ID } from '@features/automation/public.ts';
import type { AutomationCalendarSettings } from '@pages/automation/types.ts';

interface ModalUi {
    firstDaySelect: HTMLSelectElement;
    weekNumbersToggle: HTMLInputElement;
    weekNumberingSelect: HTMLSelectElement;
    timeFormatSelect: HTMLSelectElement;
    rangeTitleFormatSelect: HTMLSelectElement;
    rangeTitleWeekdayToggle: HTMLInputElement;
    error: HTMLElement;
}

interface ModalControllerDependencies {
    requireHTMLElement: (selector: string, context?: Element | Document | null) => HTMLElement;
    modalPresenter: ModalPresenterApi;
}

class AutomationCalendarSettingsModalController {
    readonly #dependencies: ModalControllerDependencies;
    readonly #modalId = AUTOMATION_CALENDAR_SETTINGS_MODAL_ID;
    readonly #ui: ModalUi;

    constructor(dependencies: ModalControllerDependencies) {
        this.#dependencies = dependencies;
        const modal = dependencies.modalPresenter.requireElement(this.#modalId);
        this.#ui = {
            firstDaySelect: narrowSelect(dependencies.requireHTMLElement(modalUiSelector(this.#modalId, 'first-day-select'), modal), 'Automation calendar settings first day'),
            weekNumbersToggle: narrowInput(dependencies.requireHTMLElement(modalUiSelector(this.#modalId, 'week-numbers-toggle'), modal), 'Automation calendar settings week numbers toggle'),
            weekNumberingSelect: narrowSelect(dependencies.requireHTMLElement(modalUiSelector(this.#modalId, 'week-numbering-select'), modal), 'Automation calendar settings week numbering'),
            timeFormatSelect: narrowSelect(dependencies.requireHTMLElement(modalUiSelector(this.#modalId, 'time-format-select'), modal), 'Automation calendar settings time format'),
            rangeTitleFormatSelect: narrowSelect(dependencies.requireHTMLElement(modalUiSelector(this.#modalId, 'range-title-format-select'), modal), 'Automation calendar settings range title format'),
            rangeTitleWeekdayToggle: narrowInput(dependencies.requireHTMLElement(modalUiSelector(this.#modalId, 'range-title-weekday-toggle'), modal), 'Automation calendar settings range title weekday toggle'),
            error: dependencies.requireHTMLElement(modalUiSelector(this.#modalId, 'error'), modal)
        };
    }

    connect(signal: AbortSignal): void {
        const sync = (): void => {
            this.#ui.weekNumberingSelect.disabled = !this.#ui.weekNumbersToggle.checked;
        };
        sync();
        const handleWeekNumbersToggleChange = (): void => sync();
        this.#ui.weekNumbersToggle.addEventListener('change', handleWeekNumbersToggleChange, { signal });
    }

    open(settings: AutomationCalendarSettings): void {
        setSelectValueAndSyncDefault(this.#ui.firstDaySelect, settings.firstDayOfWeek);
        this.#ui.weekNumbersToggle.checked = settings.showWeekNumbers;
        setSelectValueAndSyncDefault(this.#ui.weekNumberingSelect, settings.weekNumbering);
        setSelectValueAndSyncDefault(this.#ui.timeFormatSelect, settings.timeFormat);
        setSelectValueAndSyncDefault(this.#ui.rangeTitleFormatSelect, settings.rangeTitleFormat);
        this.#ui.rangeTitleWeekdayToggle.checked = settings.showRangeTitleWeekday;
        this.#ui.weekNumberingSelect.disabled = !settings.showWeekNumbers;
        this.#hideError();
        this.#dependencies.modalPresenter.open(this.#modalId);
    }

    isOpen(): boolean {
        return this.#dependencies.modalPresenter.isOpen(this.#modalId);
    }

    close(): void {
        this.#dependencies.modalPresenter.close(this.#modalId, { reason: 'automation:calendar-settings:close' });
    }

    getSnapshotKey(): string {
        return JSON.stringify({
            firstDayOfWeek: readTrimmedSelectValue(this.#ui.firstDaySelect),
            showWeekNumbers: this.#ui.weekNumbersToggle.checked,
            weekNumbering: readTrimmedSelectValue(this.#ui.weekNumberingSelect),
            timeFormat: readTrimmedSelectValue(this.#ui.timeFormatSelect),
            rangeTitleFormat: readTrimmedSelectValue(this.#ui.rangeTitleFormatSelect),
            showRangeTitleWeekday: this.#ui.rangeTitleWeekdayToggle.checked
        });
    }

    isValid(): boolean {
        const firstDay = isAutomationCalendarFirstDay(this.#ui.firstDaySelect.value);
        const weekNumbering = isAutomationCalendarWeekNumbering(this.#ui.weekNumberingSelect.value);
        const timeFormat = isAutomationCalendarTimeFormat(this.#ui.timeFormatSelect.value);
        const rangeTitleFormat = isAutomationCalendarRangeTitleFormat(this.#ui.rangeTitleFormatSelect.value);
        return Boolean(firstDay && weekNumbering && timeFormat && rangeTitleFormat);
    }

    readAndValidate(): AutomationCalendarSettings | null {
        const firstDay = this.#ui.firstDaySelect.value;
        const weekNumbering = this.#ui.weekNumberingSelect.value;
        const timeFormat = this.#ui.timeFormatSelect.value;
        const rangeTitleFormat = this.#ui.rangeTitleFormatSelect.value;

        if (!isAutomationCalendarFirstDay(firstDay) || !isAutomationCalendarWeekNumbering(weekNumbering) || !isAutomationCalendarTimeFormat(timeFormat) || !isAutomationCalendarRangeTitleFormat(rangeTitleFormat)) {
            this.#showError(i18n.t('automation.calendarSettings.validation.invalid'));
            return null;
        }

        this.#hideError();
        return {
            firstDayOfWeek: firstDay,
            showWeekNumbers: this.#ui.weekNumbersToggle.checked,
            weekNumbering,
            timeFormat,
            rangeTitleFormat,
            showRangeTitleWeekday: this.#ui.rangeTitleWeekdayToggle.checked
        };
    }

    #showError(message: string): void {
        setStatusSurface({
            surface: this.#ui.error,
            message
        });
    }

    #hideError(): void {
        clearStatusSurface(this.#ui.error);
    }
}

export { AutomationCalendarSettingsModalController };
