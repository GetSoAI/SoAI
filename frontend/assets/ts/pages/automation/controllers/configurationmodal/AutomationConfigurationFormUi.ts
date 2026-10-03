/* SoAI - Automation page configuration form UI [frontend/assets/ts/pages/automation/controllers/configurationmodal/AutomationConfigurationFormUi.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { narrowButton, narrowInput, narrowSelect } from '@core/dom/narrowElement.ts';
import { replaceSelectOptions, type SelectOptionDefinition } from '@core/dom/selectOptions.ts';
import { setSelectValueAndSyncDefault } from '@core/dom/selectSelection.ts';
import { i18n } from '@core/i18n/index.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { listSupportedTimezones, resolveBrowserTimezone } from '@core/timezones/timezones.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import type { AutomationEditorIssueField } from '@pages/automation/controllers/configurationmodal/AutomationEditorValidationDomain.ts';
import { queryAutomationColorInputs } from '@pages/automation/dom.ts';

interface AutomationConfigurationFormUiDependencies {
    requireHTMLElement: (selector: string, context?: Element | Document | null) => HTMLElement;
    modal: HTMLElement;
}

interface AutomationConfigurationFieldErrorTarget {
    control: HTMLElement;
    message: HTMLElement;
}

const AUTOMATION_TIMEZONE_AUTO = 'auto';

const ensureRadioInput = (input: HTMLInputElement, label: string): HTMLInputElement => {
    if (input.type === 'radio') {
        return input;
    }
    throw new Error(`Automation modal ${label} must be a radio input`);
};

class AutomationConfigurationFormUi {
    readonly modalRoot: HTMLElement;
    readonly formRegion: HTMLElement;
    readonly titleInput: HTMLInputElement;
    readonly colorPicker: HTMLElement;
    readonly colorInputs: HTMLInputElement[];
    readonly timezoneSelect: HTMLSelectElement;
    readonly startInput: HTMLInputElement;
    readonly recurrenceSelect: HTMLSelectElement;
    readonly scheduleSummary: HTMLElement;
    readonly modelSelect: HTMLSelectElement;
    readonly workspacePathInput: HTMLInputElement;
    readonly workspaceChangeButton: HTMLButtonElement;
    readonly parametersSummaryInput: HTMLInputElement;
    readonly parametersButton: HTMLButtonElement;
    readonly interactiveToolApprovalToggle: HTMLInputElement;
    readonly maxRunMinutesInput: HTMLInputElement;
    readonly turnsCharCounter: HTMLElement;
    readonly turnsList: HTMLElement;
    readonly addTurnButton: HTMLButtonElement;
    readonly validationSummary: HTMLElement;
    readonly fieldErrors: Readonly<Record<AutomationEditorIssueField, AutomationConfigurationFieldErrorTarget>>;

    constructor(dependencies: AutomationConfigurationFormUiDependencies) {
        const modal = dependencies.modal;
        const modalId = modal.id;
        const requireElement = (token: string): HTMLElement => dependencies.requireHTMLElement(modalUiSelector(modalId, token), modal);
        this.modalRoot = modal;
        this.formRegion = requireElement('form');
        this.titleInput = narrowInput(requireElement('title-input'), 'Automation modal title');
        this.colorPicker = requireElement('color-select');
        this.colorInputs = queryAutomationColorInputs(modalId, this.colorPicker).map((element) => ensureRadioInput(element, 'color option'));
        if (this.colorInputs.length === 0) {
            throw new Error('Automation modal color picker must contain at least one radio option');
        }
        this.timezoneSelect = narrowSelect(requireElement('timezone-select'), 'Automation modal timezone');
        this.startInput = narrowInput(requireElement('start-input'), 'Automation modal start');
        this.recurrenceSelect = narrowSelect(requireElement('recurrence-select'), 'Automation modal recurrence');
        this.scheduleSummary = requireElement('schedule-summary');
        this.modelSelect = narrowSelect(requireElement('model-input'), 'Automation modal model');
        this.workspacePathInput = narrowInput(requireElement('workspace-path-input'), 'Automation modal workspace path');
        this.workspaceChangeButton = narrowButton(requireElement('workspace-change-button'), 'Automation modal workspace button');
        this.parametersSummaryInput = narrowInput(requireElement('parameters-summary-input'), 'Automation modal parameters summary');
        this.parametersButton = narrowButton(requireElement('parameters-button'), 'Automation modal parameters button');
        this.interactiveToolApprovalToggle = narrowInput(requireElement('interactive-tool-approval-toggle'), 'Automation modal interactive tool approval');
        this.maxRunMinutesInput = narrowInput(requireElement('max-run-minutes-input'), 'Automation modal max run minutes');
        this.turnsCharCounter = requireElement('turns-char-counter');
        this.turnsList = requireElement('turns-list');
        this.addTurnButton = narrowButton(requireElement('add-turn-button'), 'Automation modal add turn button');
        this.validationSummary = requireElement('modal-error');
        this.fieldErrors = {
            title: { control: this.titleInput, message: requireElement('title-error') },
            timezone: { control: this.timezoneSelect, message: requireElement('timezone-error') },
            start: { control: this.startInput, message: requireElement('start-error') },
            recurrence: { control: this.recurrenceSelect, message: requireElement('recurrence-error') },
            model: { control: this.modelSelect, message: requireElement('model-error') },
            maxRunMinutes: { control: this.maxRunMinutesInput, message: requireElement('max-run-minutes-error') },
            turns: { control: this.turnsList, message: requireElement('turns-error') },
            mcp: { control: requireElement('mcp-tools-list'), message: requireElement('mcp-error') }
        };
        this.fieldErrors.mcp.control.tabIndex = -1;
        this.#populateTimezones(AUTOMATION_TIMEZONE_AUTO);
    }

    #populateTimezones(selectedTimezone: string): void {
        const autoLabel = i18n.t('automation.modal.timezone.autoWithZone', { timezone: resolveBrowserTimezone() });
        const supportedTimezones = listSupportedTimezones();
        const entries: SelectOptionDefinition[] = [{ value: AUTOMATION_TIMEZONE_AUTO, label: autoLabel, selected: selectedTimezone === AUTOMATION_TIMEZONE_AUTO }, ...supportedTimezones.map((timezone) => ({ value: timezone, label: timezone, selected: timezone === selectedTimezone }))];
        if (selectedTimezone !== AUTOMATION_TIMEZONE_AUTO && !supportedTimezones.includes(selectedTimezone)) {
            entries.push({ value: selectedTimezone, label: selectedTimezone, selected: true });
        }
        replaceSelectOptions(this.timezoneSelect, entries);
    }

    setTimezoneValue(value: string): void {
        this.#populateTimezones(value);
        setSelectValueAndSyncDefault(this.timezoneSelect, value);
    }

    readTimezoneValue(): string {
        const selection = this.timezoneSelect.value.trim();
        return selection === AUTOMATION_TIMEZONE_AUTO ? resolveBrowserTimezone() : selection;
    }

    readColorValue(): string {
        const selected = this.colorInputs.find((input) => input.checked);
        return selected ? selected.value : '';
    }

    setColorValue(value: string | null): void {
        const normalized = value ?? '';
        const selected = this.colorInputs.find((input) => input.value === normalized) ?? this.colorInputs[0];
        if (!selected) {
            throw new Error('Automation modal color picker is not available');
        }
        this.colorInputs.forEach((input) => {
            input.checked = input === selected;
        });
    }

    setReadOnly(readOnly: boolean): void {
        this.titleInput.readOnly = readOnly;
        this.colorInputs.forEach((input) => {
            input.disabled = readOnly;
        });
        this.colorPicker.classList.toggle('is-readonly', readOnly);
        this.timezoneSelect.disabled = readOnly;
        this.startInput.disabled = readOnly;
        this.recurrenceSelect.disabled = readOnly;
        this.modelSelect.disabled = readOnly;
        this.workspaceChangeButton.disabled = false;
        const workspaceLabel = readOnly ? i18n.t('automation.modal.workspace.viewButton') : i18n.t('automation.modal.workspace.button');
        this.workspaceChangeButton.textContent = workspaceLabel;
        this.workspaceChangeButton.setAttribute('aria-label', workspaceLabel);
        setTooltipText(this.workspaceChangeButton, workspaceLabel);
        const parametersLabel = readOnly ? i18n.t('automation.modal.parameters.viewButton') : i18n.t('automation.modal.parameters.button');
        this.parametersButton.textContent = parametersLabel;
        this.parametersButton.setAttribute('aria-label', parametersLabel);
        setTooltipText(this.parametersButton, parametersLabel);
        this.interactiveToolApprovalToggle.disabled = readOnly;
        this.maxRunMinutesInput.readOnly = readOnly;
        this.addTurnButton.classList.toggle('u-hidden', readOnly);
        this.addTurnButton.disabled = readOnly;
    }
}

export { AUTOMATION_TIMEZONE_AUTO, AutomationConfigurationFormUi };
export type { AutomationConfigurationFieldErrorTarget };
