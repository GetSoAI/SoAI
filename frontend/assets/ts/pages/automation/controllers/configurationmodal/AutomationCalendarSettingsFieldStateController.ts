/* SoAI - Automation calendar settings modal field state overlays [frontend/assets/ts/pages/automation/controllers/configurationmodal/AutomationCalendarSettingsFieldStateController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAutomationCalendarFirstDay, isAutomationCalendarRangeTitleFormat, isAutomationCalendarTimeFormat, isAutomationCalendarWeekNumbering } from '@core/automation/guards.ts';
import { readTrimmedSelectValue } from '@core/dom/formValues.ts';
import { dom } from '@core/dom/dom.ts';
import { FieldStateTracker } from '@core/forms/fieldStateTracker.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { AUTOMATION_CALENDAR_SETTINGS_MODAL_ID } from '@features/automation/public.ts';

const FIELD_KEYS = Object.freeze(['firstDay', 'weekNumbers', 'weekNumbering', 'timeFormat', 'rangeTitleFormat', 'rangeTitleWeekday']);
const selectorForField = (key: string): string => `.setting-change-surface[data-automation-calendar-field="${key}"]`;

class AutomationCalendarSettingsFieldStateController {
    readonly #modal: HTMLElement;
    readonly #tracker: FieldStateTracker;
    readonly #baseline = new Map<string, string>();

    constructor(modal: HTMLElement) {
        this.#modal = modal;
        this.#tracker = new FieldStateTracker({
            getElement: (key: string) => dom.resolve(selectorForField(key), this.#modal),
            getCurrentValue: (key: string) => this.#readValue(key),
            getOriginalValue: (key: string) => this.#baseline.get(key) ?? ''
        });
        this.#resetBaseline();
    }

    resetBaseline(): void {
        this.#resetBaseline();
    }

    #resetBaseline(): void {
        this.#baseline.clear();
        for (const key of FIELD_KEYS) {
            this.#baseline.set(key, this.#readValue(key));
        }
        this.#sync();
    }

    sync(): void {
        this.#sync();
    }

    #sync(): void {
        for (const key of FIELD_KEYS) {
            this.#tracker.update(key);
            this.#tracker.setInvalid(key, this.#isInvalid(key) ? 'invalid' : null);
        }
    }

    clear(): void {
        this.#tracker.clearAll();
        this.#baseline.clear();
    }

    #input(token: string): HTMLInputElement | null {
        const element = dom.resolve(modalUiSelector(AUTOMATION_CALENDAR_SETTINGS_MODAL_ID, token), this.#modal);
        return element instanceof HTMLInputElement ? element : null;
    }

    #select(token: string): HTMLSelectElement | null {
        const element = dom.resolve(modalUiSelector(AUTOMATION_CALENDAR_SETTINGS_MODAL_ID, token), this.#modal);
        return element instanceof HTMLSelectElement ? element : null;
    }

    #selectValue(token: string): string {
        const select = this.#select(token);
        return select ? readTrimmedSelectValue(select) : '';
    }

    #readValue(key: string): string {
        if (key === 'firstDay') return this.#selectValue('first-day-select');
        if (key === 'weekNumbers') return this.#input('week-numbers-toggle')?.checked === true ? '1' : '0';
        if (key === 'weekNumbering') return this.#selectValue('week-numbering-select');
        if (key === 'timeFormat') return this.#selectValue('time-format-select');
        if (key === 'rangeTitleFormat') return this.#selectValue('range-title-format-select');
        if (key === 'rangeTitleWeekday') return this.#input('range-title-weekday-toggle')?.checked === true ? '1' : '0';
        return '';
    }

    #isInvalid(key: string): boolean {
        if (key === 'firstDay') return !isAutomationCalendarFirstDay(this.#readValue(key));
        if (key === 'weekNumbering') return !isAutomationCalendarWeekNumbering(this.#readValue(key));
        if (key === 'timeFormat') return !isAutomationCalendarTimeFormat(this.#readValue(key));
        if (key === 'rangeTitleFormat') return !isAutomationCalendarRangeTitleFormat(this.#readValue(key));
        return false;
    }
}

export { AutomationCalendarSettingsFieldStateController };
