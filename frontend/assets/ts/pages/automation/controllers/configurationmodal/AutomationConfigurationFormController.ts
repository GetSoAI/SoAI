/* SoAI - Automation page configuration form controller [frontend/assets/ts/pages/automation/controllers/configurationmodal/AutomationConfigurationFormController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readTrimmedInputValue, readTrimmedSelectValue } from '@core/dom/formValues.ts';
import { deepEqual } from '@core/primitives/equality.ts';
import { setSelectValueAndSyncDefault } from '@core/dom/selectSelection.ts';
import { readBoundedPositiveIntegerTextOrNullValue } from '@core/types/payloadNumberReaders.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { ReadOnlyFileBrowserApi } from '@core/fileexplorerbrowser/types.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { DEFAULT_AUTOMATION_CONFIGURATION_LIMITS, HARD_MAX_RUN_MINUTES, normalizeAutomationColorSelection } from '@pages/automation/controllers/configurationmodal/AutomationConfigurationFormModel.ts';
import { AutomationConfigurationFormUi, type AutomationConfigurationFieldErrorTarget } from '@pages/automation/controllers/configurationmodal/AutomationConfigurationFormUi.ts';
import { AutomationConfigurationModelSettingsController } from '@pages/automation/controllers/configurationmodal/AutomationConfigurationModelSettingsController.ts';
import { AutomationConfigurationTurnsController } from '@pages/automation/controllers/configurationmodal/AutomationConfigurationTurnsController.ts';
import type { AutomationEditorDraft } from '@pages/automation/controllers/configurationmodal/AutomationEditorDraftDomain.ts';
import { validateAutomationEditorDraft, type AutomationEditorIssueField, type AutomationEditorValidation } from '@pages/automation/controllers/configurationmodal/AutomationEditorValidationDomain.ts';
import { AutomationSchedulePreviewController } from '@pages/automation/controllers/configurationmodal/AutomationSchedulePreviewController.ts';
import type { AutomationCreateDefaults } from '@pages/automation/state/AutomationCreateDefaultsManager.ts';
import type { AutomationDefinitionResponse, AutomationMcpCatalogResponse, AutomationModelOption, AutomationSchedulePreviewResponse, AutomationSchedulePreviewRequest } from '@features/automation/public.ts';
import type { AutomationCalendarSettings } from '@pages/automation/types.ts';

interface FormControllerDependencies {
    requireHTMLElement: (selector: string, context?: Element | Document | null) => HTMLElement;
    modal: HTMLElement;
    modalPresenter: ModalPresenterApi;
    getIconSync: (icon: IconName, options?: IconOptions) => TrustedHtml;
    previewSchedule: (input: AutomationSchedulePreviewRequest, signal?: AbortSignal) => Promise<AutomationSchedulePreviewResponse>;
    getCalendarSettings: () => AutomationCalendarSettings;
}

interface AutomationCreateValues {
    startLocal: string;
    timezone: string;
    createDefaults: AutomationCreateDefaults;
    currentWorkspacePath: string;
}

class AutomationConfigurationFormController {
    readonly #ui: AutomationConfigurationFormUi;
    readonly #turns: AutomationConfigurationTurnsController;
    readonly #modelSettings: AutomationConfigurationModelSettingsController;
    readonly #schedulePreview: AutomationSchedulePreviewController;
    readonly #abort = new AbortController();
    #readOnly = false;
    #enabled = true;
    #currentWorkspacePath = '';
    #turnBaseline: { turns: readonly string[]; maxTurns: number; maxTurnChars: number } | null = null;

    constructor(dependencies: FormControllerDependencies) {
        this.#ui = new AutomationConfigurationFormUi(dependencies);
        this.#turns = new AutomationConfigurationTurnsController({ addTurnButton: this.#ui.addTurnButton, modalId: dependencies.modal.id, turnsList: this.#ui.turnsList, turnsCharCounter: this.#ui.turnsCharCounter });
        this.#modelSettings = new AutomationConfigurationModelSettingsController({
            modalRoot: this.#ui.modalRoot,
            modelSelect: this.#ui.modelSelect,
            workspacePathInput: this.#ui.workspacePathInput,
            parametersSummaryInput: this.#ui.parametersSummaryInput,
            modalPresenter: dependencies.modalPresenter,
            getIconSync: dependencies.getIconSync
        });
        this.#schedulePreview = new AutomationSchedulePreviewController({
            summary: this.#ui.scheduleSummary,
            eventTarget: this.#ui.modalRoot,
            readSchedule: () => ({ startLocal: readTrimmedInputValue(this.#ui.startInput), timezone: this.#ui.readTimezoneValue(), recurrence: readTrimmedSelectValue(this.#ui.recurrenceSelect) }),
            isEnabled: () => this.#enabled,
            previewSchedule: dependencies.previewSchedule,
            getCalendarSettings: dependencies.getCalendarSettings
        });
        const refreshSchedule = (): void => this.#schedulePreview.refresh();
        for (const control of [this.#ui.startInput, this.#ui.timezoneSelect, this.#ui.recurrenceSelect]) {
            control.addEventListener('input', refreshSchedule, { signal: this.#abort.signal });
            control.addEventListener('change', refreshSchedule, { signal: this.#abort.signal });
        }
    }

    getFormRegion(): HTMLElement {
        return this.#ui.formRegion;
    }

    getFieldErrorTargets(): Readonly<Record<AutomationEditorIssueField, AutomationConfigurationFieldErrorTarget>> {
        return this.#ui.fieldErrors;
    }

    getValidationSummary(): HTMLElement {
        return this.#ui.validationSummary;
    }

    listTurnTextareas(): HTMLTextAreaElement[] {
        return this.#turns.listTextareas();
    }

    setAvailableModels(models: readonly AutomationModelOption[]): void {
        this.#modelSettings.setAvailableModels(models);
    }

    setMcpCatalog(catalog: AutomationMcpCatalogResponse): void {
        this.#modelSettings.setMcpCatalog(catalog);
    }

    setCreateValues(values: AutomationCreateValues): void {
        this.#currentWorkspacePath = values.currentWorkspacePath;
        this.#turnBaseline = null;
        this.#ui.titleInput.value = '';
        this.#ui.setColorValue('');
        this.#enabled = true;
        this.#ui.interactiveToolApprovalToggle.checked = values.createDefaults.interactiveToolApproval;
        this.#ui.setTimezoneValue(values.timezone);
        this.#ui.startInput.value = values.startLocal;
        setSelectValueAndSyncDefault(this.#ui.recurrenceSelect, 'none');
        this.#ui.maxRunMinutesInput.value = String(DEFAULT_AUTOMATION_CONFIGURATION_LIMITS.maxRunMinutes);
        this.#modelSettings.setValues({ model: '', agent: { mode: 'execute' }, mcp: this.#createDefaultMcpConfig(values.createDefaults), workspacePath: values.currentWorkspacePath }, values.currentWorkspacePath);
        this.#turns.renderTurns(['']);
        this.#resetSchedulePreview();
    }

    setEditValues(automation: AutomationDefinitionResponse, currentWorkspacePath: string = this.#currentWorkspacePath): void {
        this.#currentWorkspacePath = currentWorkspacePath;
        this.applyDraft(automation);
        this.#enabled = automation.enabled;
        this.#resetSchedulePreview();
        this.#schedulePreview.preserveSchedule({ startLocal: automation.startLocal, timezone: automation.timezone, recurrence: automation.recurrence, enabled: automation.enabled }, automation.nextRunAtMs);
    }

    applyDraft(automation: AutomationEditorDraft): void {
        this.#ui.titleInput.value = automation.title;
        this.#ui.setColorValue(automation.color ?? '');
        this.#ui.interactiveToolApprovalToggle.checked = automation.interactiveToolApproval;
        this.#ui.setTimezoneValue(automation.timezone);
        this.#ui.startInput.value = automation.startLocal;
        setSelectValueAndSyncDefault(this.#ui.recurrenceSelect, automation.recurrence);
        this.#ui.maxRunMinutesInput.value = automation.maxRunMinutes === null ? '' : String(automation.maxRunMinutes);
        this.#modelSettings.setValues(automation.modelSettings, this.#currentWorkspacePath);
        this.#turnBaseline = { turns: [...automation.turns], maxTurns: automation.maxTurns, maxTurnChars: automation.maxTurnChars };
        this.#turns.renderTurns(automation.turns);
        this.#schedulePreview.refresh();
    }

    setReadOnlyMode(readOnly: boolean): void {
        this.#readOnly = readOnly;
        this.#ui.setReadOnly(readOnly);
        this.#modelSettings.setReadOnly(readOnly);
        this.#turns.setReadOnly(readOnly);
    }

    endSession(): void {
        this.#schedulePreview.reset();
    }

    destroy(): void {
        this.#abort.abort();
        this.#schedulePreview.reset();
        this.#modelSettings.destroy();
        this.#turns.destroy();
    }

    addTurn(): void {
        this.#turns.addTurn();
    }

    removeTurn(indexCandidate: string | null): void {
        this.#turns.removeTurn(indexCandidate);
    }

    async openWorkspaceModal(api: ReadOnlyFileBrowserApi, canApply: () => boolean, signal?: AbortSignal): Promise<boolean> {
        return await this.#modelSettings.openWorkspaceModal(api, canApply, signal);
    }

    async openParametersModal(canApply: () => boolean, signal?: AbortSignal): Promise<boolean> {
        return await this.#modelSettings.openParametersModal(canApply, signal);
    }

    readDraft(): AutomationEditorDraft {
        const interactiveToolApproval = this.#ui.interactiveToolApprovalToggle.checked;
        const modelSettings = this.#modelSettings.readModelSettings();
        modelSettings.mcp = { ...modelSettings.mcp, toolApprovalRequired: interactiveToolApproval };
        const turns = this.#turns.readNormalizedTurns();
        const preservedLimits = this.#turnBaseline !== null && deepEqual(turns, this.#turnBaseline.turns) ? this.#turnBaseline : null;
        return {
            title: readTrimmedInputValue(this.#ui.titleInput),
            color: normalizeAutomationColorSelection(this.#ui.readColorValue()),
            interactiveToolApproval,
            timezone: this.#ui.readTimezoneValue(),
            startLocal: readTrimmedInputValue(this.#ui.startInput),
            recurrence: readTrimmedSelectValue(this.#ui.recurrenceSelect),
            maxRunMinutes: readBoundedPositiveIntegerTextOrNullValue(this.#ui.maxRunMinutesInput.value, HARD_MAX_RUN_MINUTES),
            modelSettings,
            turns,
            maxTurns: preservedLimits !== null ? preservedLimits.maxTurns : turns.length,
            maxTurnChars: preservedLimits !== null ? preservedLimits.maxTurnChars : Math.max(1, ...turns.map((turn) => turn.length))
        };
    }

    validate(): AutomationEditorValidation {
        return validateAutomationEditorDraft(this.readDraft(), {
            modelIssue: this.#modelSettings.getModelIssue(),
            timezoneIssue: this.#readOnly ? null : this.#schedulePreview.getTimezoneIssue(),
            scheduleIssue: this.#readOnly ? null : this.#schedulePreview.getScheduleIssue()
        });
    }

    #resetSchedulePreview(): void {
        this.#schedulePreview.reset();
        this.#schedulePreview.refresh();
    }

    #createDefaultMcpConfig(defaults: AutomationCreateDefaults): AutomationDefinitionResponse['modelSettings']['mcp'] {
        return {
            defaultTools: [],
            planTools: [],
            executeTools: [...defaults.executeTools],
            serverConfigs: { ...defaults.serverConfigs },
            toolsEnabled: true,
            toolApprovalRequired: defaults.interactiveToolApproval
        };
    }
}

export { AutomationConfigurationFormController };
export type { AutomationCreateValues };
