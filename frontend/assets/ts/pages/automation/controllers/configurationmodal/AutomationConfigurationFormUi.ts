/* SoAI - Automation page configuration form UI [frontend/assets/ts/pages/automation/controllers/configurationmodal/AutomationConfigurationFormUi.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { narrowButton, narrowInput, narrowSelect } from '@core/dom/narrowElement.ts';
import { i18n } from '@core/i18n/index.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { listSupportedTimezones } from '@core/timezones/timezones.ts';
import { clearStatusSurface, setStatusSurface } from '@core/ui/statusSurface.ts';
import { queryAutomationColorInputs } from '@pages/automation/dom.ts';

interface AutomationConfigurationFormUiDependencies {
    requireHTMLElement: (selector: string, context?: Element | Document | null) => HTMLElement;
    modal: HTMLElement;
}

const ensureRadioInput = (input: HTMLInputElement, label: string): HTMLInputElement => {
    if (input.type === 'radio') {
        return input;
    }
    throw new Error(`Automation modal ${label} must be a radio input`);
};

class AutomationConfigurationFormUi {
    readonly modalRoot: HTMLElement;
    readonly titleInput: HTMLInputElement;
    readonly colorPicker: HTMLElement;
    readonly colorInputs: HTMLInputElement[];
    readonly timezoneSelect: HTMLSelectElement;
    readonly startInput: HTMLInputElement;
    readonly recurrenceSelect: HTMLSelectElement;
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
    readonly error: HTMLElement;

    constructor(dependencies: AutomationConfigurationFormUiDependencies) {
        const modal = dependencies.modal;
        this.modalRoot = modal;
        const modalId = modal.id;
        this.titleInput = narrowInput(dependencies.requireHTMLElement(modalUiSelector(modalId, 'title-input'), modal), 'Automation modal title');
        this.colorPicker = dependencies.requireHTMLElement(modalUiSelector(modalId, 'color-select'), modal);
        this.colorInputs = queryAutomationColorInputs(modalId, this.colorPicker).map((element) => ensureRadioInput(element, 'color option'));
        if (this.colorInputs.length === 0) {
            throw new Error('Automation modal color picker must contain at least one radio option');
        }
        this.timezoneSelect = narrowSelect(dependencies.requireHTMLElement(modalUiSelector(modalId, 'timezone-select'), modal), 'Automation modal timezone');
        this.startInput = narrowInput(dependencies.requireHTMLElement(modalUiSelector(modalId, 'start-input'), modal), 'Automation modal start');
        this.recurrenceSelect = narrowSelect(dependencies.requireHTMLElement(modalUiSelector(modalId, 'recurrence-select'), modal), 'Automation modal recurrence');
        this.modelSelect = narrowSelect(dependencies.requireHTMLElement(modalUiSelector(modalId, 'model-input'), modal), 'Automation modal model');
        this.workspacePathInput = narrowInput(dependencies.requireHTMLElement(modalUiSelector(modalId, 'workspace-path-input'), modal), 'Automation modal workspace path');
        this.workspaceChangeButton = narrowButton(dependencies.requireHTMLElement(modalUiSelector(modalId, 'workspace-change-button'), modal), 'Automation modal workspace button');
        this.parametersSummaryInput = narrowInput(dependencies.requireHTMLElement(modalUiSelector(modalId, 'parameters-summary-input'), modal), 'Automation modal parameters summary');
        this.parametersButton = narrowButton(dependencies.requireHTMLElement(modalUiSelector(modalId, 'parameters-button'), modal), 'Automation modal parameters button');
        this.interactiveToolApprovalToggle = narrowInput(dependencies.requireHTMLElement(modalUiSelector(modalId, 'interactive-tool-approval-toggle'), modal), 'Automation modal interactive tool approval');
        this.maxRunMinutesInput = narrowInput(dependencies.requireHTMLElement(modalUiSelector(modalId, 'max-run-minutes-input'), modal), 'Automation modal max run minutes');
        this.turnsCharCounter = dependencies.requireHTMLElement(modalUiSelector(modalId, 'turns-char-counter'), modal);
        this.turnsList = dependencies.requireHTMLElement(modalUiSelector(modalId, 'turns-list'), modal);
        this.addTurnButton = narrowButton(dependencies.requireHTMLElement(modalUiSelector(modalId, 'add-turn-button'), modal), 'Automation modal add turn button');
        this.error = dependencies.requireHTMLElement(modalUiSelector(modalId, 'modal-error'), modal);

        this.#populateTimezones();
    }

    #populateTimezones(): void {
        const select = this.timezoneSelect;
        select.replaceChildren();

        const autoOption = document.createElement('option');
        autoOption.value = 'auto';
        autoOption.textContent = i18n.t('automation.modal.timezone.auto');
        select.append(autoOption);

        const zones = listSupportedTimezones();
        for (const zone of zones) {
            const option = document.createElement('option');
            option.value = zone;
            option.textContent = zone;
            select.append(option);
        }
    }

    showError(message: string): void {
        setStatusSurface({
            surface: this.error,
            message
        });
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

    hideError(): void {
        clearStatusSurface(this.error);
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
        this.workspaceChangeButton.disabled = readOnly;
        this.parametersButton.disabled = readOnly;
        this.interactiveToolApprovalToggle.disabled = readOnly;
        this.maxRunMinutesInput.readOnly = readOnly;
        this.addTurnButton.classList.toggle('u-hidden', readOnly);
        this.addTurnButton.disabled = readOnly;
    }
}

export { AutomationConfigurationFormUi };
