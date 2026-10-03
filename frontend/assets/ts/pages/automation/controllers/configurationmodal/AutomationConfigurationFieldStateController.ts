/* SoAI - Automation configuration modal field state overlays and validation messages [frontend/assets/ts/pages/automation/controllers/configurationmodal/AutomationConfigurationFieldStateController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readTrimmedInputValue, readTrimmedSelectValue } from '@core/dom/formValues.ts';
import { dom } from '@core/dom/dom.ts';
import { FIELD_MODIFIED_CLASS } from '@core/forms/fieldSurface.ts';
import { FieldStateTracker } from '@core/forms/fieldStateTracker.ts';
import { i18n } from '@core/i18n/index.ts';
import { clearMcpToolChangeSurfaces, syncMcpToolChangeSurfaces } from '@core/mcp/toolChangeSurfaces.ts';
import type { McpFormValues } from '@core/mcp/configTypes.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { setFieldErrorMessage } from '@core/ui/forms/fieldError.ts';
import { clearStatusSurface, setStatusSurface } from '@core/ui/statusSurface.ts';
import { AUTOMATION_CONFIGURATION_MODAL_ID } from '@features/automation/public.ts';
import type { AutomationConfigurationFieldErrorTarget } from '@pages/automation/controllers/configurationmodal/AutomationConfigurationFormUi.ts';
import { AUTOMATION_EDITOR_ISSUE_FIELDS, type AutomationEditorIssueField, type AutomationEditorValidation } from '@pages/automation/controllers/configurationmodal/AutomationEditorValidationDomain.ts';

const FIELD_KEYS = Object.freeze(['title', 'color', 'timezone', 'start', 'recurrence', 'model', 'workspace', 'parameters', 'interactiveToolApproval', 'maxRunMinutes', 'turns']);
const FIELD_KEY_SET = new Set<string>(FIELD_KEYS);
const selectorForField = (key: string): string => `.setting-change-surface[data-automation-field="${key}"]`;

interface AutomationConfigurationFieldStateDependencies {
    modal: HTMLElement;
    fieldErrors: Readonly<Record<AutomationEditorIssueField, AutomationConfigurationFieldErrorTarget>>;
    validationSummary: HTMLElement;
    listTurnTextareas: () => HTMLTextAreaElement[];
    readMcpConfig: () => McpFormValues;
    validate: () => AutomationEditorValidation;
}

class AutomationConfigurationFieldStateController {
    readonly #dependencies: AutomationConfigurationFieldStateDependencies;
    readonly #modal: HTMLElement;
    readonly #tracker: FieldStateTracker;
    readonly #baseline = new Map<string, string>();
    readonly #touched = new Set<string>();
    #mcpBaseline: McpFormValues | null = null;
    #revealAll = false;

    constructor(dependencies: AutomationConfigurationFieldStateDependencies) {
        this.#dependencies = dependencies;
        this.#modal = dependencies.modal;
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
        this.#revealAll = false;
        for (const key of FIELD_KEYS) {
            this.#baseline.set(key, this.#readValue(key));
        }
        this.#mcpBaseline = this.#readMcpValues();
        this.sync();
    }

    markTouchedFromEvent(event: Event): boolean {
        const target = event.target;
        if (!(target instanceof Element)) {
            return false;
        }
        const surface = target.closest('.setting-change-surface[data-automation-field]');
        const key = surface instanceof HTMLElement ? (surface.dataset['automationField'] ?? '') : '';
        if (key === 'mcp') {
            this.#touched.add(key);
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

    revealAllIssues(validation: AutomationEditorValidation): void {
        this.#revealAll = true;
        this.sync(validation);
        const firstIssue = AUTOMATION_EDITOR_ISSUE_FIELDS.find((field) => validation.issues.some((issue) => issue.field === field));
        if (firstIssue === undefined) {
            return;
        }
        const focusTarget = firstIssue === 'turns' ? this.#dependencies.listTurnTextareas()[validation.invalidTurnIndexes[0] ?? 0] : this.#dependencies.fieldErrors[firstIssue].control;
        focusTarget?.focus();
    }

    sync(validation: AutomationEditorValidation = this.#dependencies.validate()): AutomationEditorValidation {
        const invalidTurns = new Set(validation.invalidTurnIndexes);
        for (const key of FIELD_KEYS) {
            this.#tracker.update(key);
        }
        for (const field of AUTOMATION_EDITOR_ISSUE_FIELDS) {
            const issue = validation.issues.find((candidate) => candidate.field === field) ?? null;
            const visibleMessage = issue && (this.#revealAll || this.#touched.has(field)) ? issue.message : null;
            this.#tracker.setInvalid(field, visibleMessage);
            const target = this.#dependencies.fieldErrors[field];
            if (field === 'turns') {
                this.#syncTurnErrors(target, visibleMessage, invalidTurns);
                continue;
            }
            setFieldErrorMessage(target.control, target.message, visibleMessage);
        }
        if (this.#revealAll && validation.issues.length > 0) {
            setStatusSurface({ surface: this.#dependencies.validationSummary, message: i18n.t('automation.modal.validation.summary', { count: validation.issues.length }) });
        } else {
            clearStatusSurface(this.#dependencies.validationSummary);
        }
        syncMcpToolChangeSurfaces({ modalRoot: this.#modal, baseline: this.#mcpBaseline, current: this.#readMcpValues() });
        dom.resolve(selectorForField('mcp'), this.#modal)?.classList.remove(FIELD_MODIFIED_CLASS);
        return validation;
    }

    clear(): void {
        this.#tracker.clearAll();
        this.#baseline.clear();
        this.#touched.clear();
        this.#revealAll = false;
        this.#mcpBaseline = null;
        for (const field of AUTOMATION_EDITOR_ISSUE_FIELDS) {
            const target = this.#dependencies.fieldErrors[field];
            if (field === 'turns') {
                this.#syncTurnErrors(target, null, new Set());
                continue;
            }
            setFieldErrorMessage(target.control, target.message, null);
        }
        clearStatusSurface(this.#dependencies.validationSummary);
        clearMcpToolChangeSurfaces(this.#modal);
        dom.resolve(selectorForField('mcp'), this.#modal)?.classList.remove(FIELD_MODIFIED_CLASS);
    }

    #syncTurnErrors(target: AutomationConfigurationFieldErrorTarget, message: string | null, invalidTurns: ReadonlySet<number>): void {
        setFieldErrorMessage(target.control, target.message, message);
        this.#dependencies.listTurnTextareas().forEach((textarea, index) => {
            const error = dom.resolve(`[id="${textarea.id}-error"]`, this.#modal);
            if (!(error instanceof HTMLElement)) throw new Error('Automation turn error target missing');
            setFieldErrorMessage(textarea, error, message !== null && invalidTurns.has(index) ? message : null);
        });
    }

    #input(token: string): HTMLInputElement | null {
        const element = dom.resolve(modalUiSelector(AUTOMATION_CONFIGURATION_MODAL_ID, token), this.#modal);
        return element instanceof HTMLInputElement ? element : null;
    }

    #inputValue(token: string): string {
        const input = this.#input(token);
        return input ? readTrimmedInputValue(input) : '';
    }

    #selectValue(token: string): string {
        const select = dom.resolve(modalUiSelector(AUTOMATION_CONFIGURATION_MODAL_ID, token), this.#modal);
        return select instanceof HTMLSelectElement ? readTrimmedSelectValue(select) : '';
    }

    #readColorValue(): string {
        const selected = dom.resolveAll('.automation-color-select input[type="radio"]', this.#modal).find((element) => element instanceof HTMLInputElement && element.checked);
        return selected instanceof HTMLInputElement ? selected.value : '';
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
        if (key === 'turns') return JSON.stringify(this.#dependencies.listTurnTextareas().map((element) => element.value.trim()));
        return '';
    }

    #readMcpValues(): McpFormValues {
        return this.#dependencies.readMcpConfig();
    }
}

export { AutomationConfigurationFieldStateController };
