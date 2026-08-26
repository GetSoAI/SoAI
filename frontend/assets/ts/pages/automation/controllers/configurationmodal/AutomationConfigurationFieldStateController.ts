/* SoAI - Automation configuration modal field state overlays [frontend/assets/ts/pages/automation/controllers/configurationmodal/AutomationConfigurationFieldStateController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readTrimmedInputValue, readTrimmedSelectValue } from '@core/dom/formValues.ts';
import { dom } from '@core/dom/dom.ts';
import { FIELD_MODIFIED_CLASS } from '@core/forms/fieldSurface.ts';
import { FieldStateTracker } from '@core/forms/fieldStateTracker.ts';
import { clearMcpToolChangeSurfaces, syncMcpToolChangeSurfaces } from '@core/mcp/toolChangeSurfaces.ts';
import type { McpFormValues } from '@core/mcp/configTypes.ts';
import { readMcpFormValues } from '@core/mcp/mcpFormController.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { parseStartLocalToDate } from '@core/time/localCalendar.ts';
import { AUTOMATION_CONFIGURATION_MODAL_ID } from '@features/automation/public.ts';
import { HARD_MAX_TURN_CHARS, resolveAutomationRecurrence } from '@pages/automation/controllers/configurationmodal/AutomationConfigurationFormModel.ts';

const FIELD_KEYS = Object.freeze(['title', 'color', 'timezone', 'start', 'recurrence', 'model', 'workspace', 'parameters', 'interactiveToolApproval', 'maxRunMinutes', 'turns']);
const FIELD_KEY_SET = new Set<string>(FIELD_KEYS);
const selectorForField = (key: string): string => `.setting-change-surface[data-automation-field="${key}"]`;

class AutomationConfigurationFieldStateController {
    readonly #modal: HTMLElement;
    readonly #tracker: FieldStateTracker;
    readonly #baseline = new Map<string, string>();
    readonly #touched = new Set<string>();
    #mcpBaseline: McpFormValues | null = null;

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
        this.#touched.clear();
        for (const key of FIELD_KEYS) {
            this.#baseline.set(key, this.#readValue(key));
        }
        this.#mcpBaseline = this.#readMcpValues();
        this.#sync();
    }

    markTouchedFromEvent(event: Event): boolean {
        const target = event.target;
        if (!(target instanceof Element)) {
            return false;
        }
        const surface = target.closest('.setting-change-surface[data-automation-field]');
        const key = surface instanceof HTMLElement ? (surface.dataset['automationField'] ?? '') : '';
        if (key === 'mcp') {
            return target instanceof HTMLInputElement && (target.classList.contains('mcp-tool-toggle') || target.classList.contains('mcp-server-toggle'));
        }
        if (FIELD_KEY_SET.has(key)) {
            this.#touched.add(key);
            return true;
        }
        return false;
    }

    markTouched(key: string): void {
        if (key) {
            this.#touched.add(key);
        }
    }

    sync(): void {
        this.#sync();
    }

    #sync(): void {
        for (const key of FIELD_KEYS) {
            this.#tracker.update(key);
            this.#tracker.setInvalid(key, this.#isInvalid(key) ? 'invalid' : null);
        }
        syncMcpToolChangeSurfaces({
            modalRoot: this.#modal,
            baseline: this.#mcpBaseline,
            current: this.#readMcpValues()
        });
        this.#clearMcpSectionSurface();
    }

    clear(): void {
        this.#tracker.clearAll();
        this.#baseline.clear();
        this.#touched.clear();
        this.#mcpBaseline = null;
        clearMcpToolChangeSurfaces(this.#modal);
        this.#clearMcpSectionSurface();
    }

    #input(token: string): HTMLInputElement | null {
        const element = dom.resolve(modalUiSelector(AUTOMATION_CONFIGURATION_MODAL_ID, token), this.#modal);
        return element instanceof HTMLInputElement ? element : null;
    }

    #select(token: string): HTMLSelectElement | null {
        const element = dom.resolve(modalUiSelector(AUTOMATION_CONFIGURATION_MODAL_ID, token), this.#modal);
        return element instanceof HTMLSelectElement ? element : null;
    }

    #inputValue(token: string): string {
        const input = this.#input(token);
        return input ? readTrimmedInputValue(input) : '';
    }

    #selectValue(token: string): string {
        const select = this.#select(token);
        return select ? readTrimmedSelectValue(select) : '';
    }

    #readValue(key: string): string {
        if (key === 'title') return this.#inputValue('title-input');
        if (key === 'color') return this.#readColorValue();
        if (key === 'timezone') return this.#selectValue('timezone-select');
        if (key === 'start') return this.#inputValue('start-input');
        if (key === 'recurrence') return this.#selectValue('recurrence-select');
        if (key === 'model') return this.#selectValue('model-input');
        if (key === 'workspace') return this.#inputValue('workspace-path-input');
        if (key === 'parameters') return this.#input('parameters-summary-input')?.dataset['parametersProjection'] ?? '';
        if (key === 'interactiveToolApproval') return this.#input('interactive-tool-approval-toggle')?.checked === true ? '1' : '0';
        if (key === 'maxRunMinutes') return this.#inputValue('max-run-minutes-input');
        if (key === 'turns') return JSON.stringify(dom.resolveAll('textarea.automation-turn-input[data-turn-index]', this.#modal).map((element) => (element instanceof HTMLTextAreaElement ? element.value.trim() : '')));
        return '';
    }

    #readMcpValues(): McpFormValues {
        return readMcpFormValues(this.#modal, { toolsEnabled: true, toolApprovalRequired: false });
    }

    #clearMcpSectionSurface(): void {
        const surface = dom.resolve(selectorForField('mcp'), this.#modal);
        surface?.classList.remove(FIELD_MODIFIED_CLASS);
    }

    #readColorValue(): string {
        const selected = dom.resolveAll('.automation-color-select input[type="radio"]', this.#modal).find((element) => element instanceof HTMLInputElement && element.checked);
        return selected instanceof HTMLInputElement ? selected.value : '';
    }

    #isInvalid(key: string): boolean {
        const touched = this.#touched.has(key);
        if (key === 'title') return touched && this.#readValue(key) === '';
        if (key === 'start') {
            const input = this.#input('start-input');
            const value = this.#readValue(key);
            return (touched && value === '') || (value !== '' && (input?.validity.valid === false || parseStartLocalToDate(value) === null));
        }
        if (key === 'recurrence') return resolveAutomationRecurrence(this.#readValue(key)) === null;
        if (key === 'model') return touched && this.#readValue(key) === '';
        if (key === 'maxRunMinutes') return this.#isNumberInputInvalid('max-run-minutes-input');
        if (key === 'turns') return touched && this.#areTurnsInvalid();
        return false;
    }

    #isNumberInputInvalid(token: string): boolean {
        const input = this.#input(token);
        return !input || (input.value.trim() !== '' && !input.validity.valid);
    }

    #areTurnsInvalid(): boolean {
        const turns = dom.resolveAll('textarea.automation-turn-input[data-turn-index]', this.#modal).filter((element): element is HTMLTextAreaElement => element instanceof HTMLTextAreaElement);
        if (turns.length === 0) {
            return true;
        }
        return turns.some((turn) => turn.value.trim().length > HARD_MAX_TURN_CHARS);
    }
}

export { AutomationConfigurationFieldStateController };
