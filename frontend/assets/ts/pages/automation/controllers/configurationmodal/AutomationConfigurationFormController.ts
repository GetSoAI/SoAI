/* SoAI - Automation page configuration form controller [frontend/assets/ts/pages/automation/controllers/configurationmodal/AutomationConfigurationFormController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readTrimmedInputValue, readTrimmedSelectValue } from '@core/dom/formValues.ts';
import { setSelectValueAndSyncDefault } from '@core/dom/selectSelection.ts';
import { i18n } from '@core/i18n/index.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { ReadOnlyFileBrowserApi } from '@core/fileexplorerbrowser/types.ts';
import { parseStartLocalToDate } from '@core/time/localCalendar.ts';
import { resolveBrowserTimezone } from '@core/timezones/timezones.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { DEFAULT_AUTOMATION_CONFIGURATION_LIMITS, HARD_MAX_TURN_CHARS, HARD_MAX_TURNS, normalizeAutomationColorSelection, resolveAutomationRecurrence, type AutomationConfigurationLimits } from '@pages/automation/controllers/configurationmodal/AutomationConfigurationFormModel.ts';
import { AutomationConfigurationFormUi } from '@pages/automation/controllers/configurationmodal/AutomationConfigurationFormUi.ts';
import { AutomationConfigurationLimitsController } from '@pages/automation/controllers/configurationmodal/AutomationConfigurationLimitsController.ts';
import { AutomationConfigurationModelSettingsController } from '@pages/automation/controllers/configurationmodal/AutomationConfigurationModelSettingsController.ts';
import { AutomationConfigurationTurnsController } from '@pages/automation/controllers/configurationmodal/AutomationConfigurationTurnsController.ts';
import { AutomationConfigurationTurnUiController } from '@pages/automation/controllers/configurationmodal/AutomationConfigurationTurnUiController.ts';
import type { AutomationCreateDefaults } from '@pages/automation/state/AutomationCreateDefaultsManager.ts';
import type { AutomationDefinition, AutomationMcpCatalog, AutomationModelOption, CreateAutomationPayload } from '@features/automation/public.ts';

interface FormControllerDependencies {
    requireHTMLElement: (selector: string, context?: Element | Document | null) => HTMLElement;
    modal: HTMLElement;
    modalPresenter: ModalPresenterApi;
    getIconSync: (icon: IconName, options?: IconOptions) => TrustedHtml;
}

class AutomationConfigurationFormController {
    readonly #ui: AutomationConfigurationFormUi;
    readonly #turns: AutomationConfigurationTurnsController;
    readonly #limits: AutomationConfigurationLimitsController;
    readonly #modelSettings: AutomationConfigurationModelSettingsController;
    readonly #turnUi: AutomationConfigurationTurnUiController;
    #readOnly = false;
    #enabled = true;

    constructor(dependencies: FormControllerDependencies) {
        this.#ui = new AutomationConfigurationFormUi(dependencies);

        this.#turns = new AutomationConfigurationTurnsController({
            turnsList: this.#ui.turnsList,
            turnsCharCounter: this.#ui.turnsCharCounter
        });
        this.#limits = new AutomationConfigurationLimitsController({
            maxRunMinutesInput: this.#ui.maxRunMinutesInput
        });
        this.#modelSettings = new AutomationConfigurationModelSettingsController({
            modalRoot: this.#ui.modalRoot,
            modelSelect: this.#ui.modelSelect,
            workspacePathInput: this.#ui.workspacePathInput,
            parametersSummaryInput: this.#ui.parametersSummaryInput,
            modalPresenter: dependencies.modalPresenter,
            getIconSync: dependencies.getIconSync
        });
        this.#turnUi = new AutomationConfigurationTurnUiController({
            addTurnButton: this.#ui.addTurnButton,
            turnsList: this.#ui.turnsList,
            turns: this.#turns
        });
    }

    setAvailableModels(models: readonly AutomationModelOption[]): void {
        this.#modelSettings.setAvailableModels(models);
    }

    setMcpCatalog(catalog: AutomationMcpCatalog): void {
        this.#modelSettings.setMcpCatalog(catalog);
    }

    setCreateValues(defaults: { startLocal: string; timezone: string; createDefaults: AutomationCreateDefaults; currentWorkspacePath: string }): void {
        this.#ui.titleInput.value = '';
        this.#ui.setColorValue('');
        this.#enabled = true;
        this.#ui.interactiveToolApprovalToggle.checked = defaults.createDefaults.interactiveToolApproval;
        setSelectValueAndSyncDefault(this.#ui.timezoneSelect, defaults.timezone);
        this.#ui.startInput.value = defaults.startLocal;
        setSelectValueAndSyncDefault(this.#ui.recurrenceSelect, 'none');
        this.#limits.setValues(DEFAULT_AUTOMATION_CONFIGURATION_LIMITS);
        this.#modelSettings.setValues(
            {
                model: '',
                agent: { mode: 'execute' },
                mcp: this.#createDefaultMcpConfig(defaults.createDefaults),
                workspacePath: defaults.currentWorkspacePath
            },
            defaults.currentWorkspacePath
        );
        this.#turns.renderTurns([''], { readOnly: false });
        this.#turnUi.sync();
        this.#ui.hideError();
    }

    setEditValues(automation: AutomationDefinition, currentWorkspacePath: string): void {
        this.#ui.titleInput.value = automation.title;
        this.#ui.setColorValue(automation.color ?? '');
        this.#enabled = automation.enabled;
        this.#ui.interactiveToolApprovalToggle.checked = automation.interactiveToolApproval;
        setSelectValueAndSyncDefault(this.#ui.timezoneSelect, automation.timezone);
        this.#ui.startInput.value = automation.startLocal;
        setSelectValueAndSyncDefault(this.#ui.recurrenceSelect, automation.recurrence);
        const limits: AutomationConfigurationLimits = { maxRunMinutes: automation.maxRunMinutes };
        this.#limits.setValues(limits);
        this.#modelSettings.setValues(automation.modelSettings, currentWorkspacePath);
        this.#turns.renderTurns(automation.turns.length ? automation.turns : [''], { readOnly: false });
        this.#turnUi.sync();
        this.#ui.hideError();
    }

    setReadOnlyMode(readOnly: boolean): void {
        this.#readOnly = readOnly;
        this.#ui.setReadOnly(readOnly);
        this.#modelSettings.setReadOnly(readOnly);
        this.#turnUi.setReadOnly(readOnly);
        const turns = this.#turns.readTurns();
        const limits = this.#limits.readAndValidate();
        if (!limits) {
            throw new Error('Automation modal limits are invalid');
        }
        this.#turns.renderTurns(turns, { readOnly });
        this.#turnUi.sync();
    }

    destroy(): void {
        this.#modelSettings.destroy();
        this.#turnUi.destroy();
    }

    addTurn(): void {
        if (this.#readOnly) {
            return;
        }
        this.#turns.addTurn();
    }

    removeTurn(indexCandidate: string | null): void {
        if (this.#readOnly) {
            return;
        }
        this.#turns.removeTurn(indexCandidate);
    }

    async openWorkspaceModal(api: ReadOnlyFileBrowserApi, canApply: () => boolean): Promise<boolean> {
        return await this.#modelSettings.openWorkspaceModal(api, canApply);
    }

    async openParametersModal(canApply: () => boolean): Promise<boolean> {
        return await this.#modelSettings.openParametersModal(canApply);
    }

    getSnapshotKey(): string {
        const timezoneSelection = readTrimmedSelectValue(this.#ui.timezoneSelect);
        const timezone = timezoneSelection === 'auto' ? resolveBrowserTimezone() : timezoneSelection;
        return JSON.stringify({
            title: readTrimmedInputValue(this.#ui.titleInput),
            color: normalizeAutomationColorSelection(this.#ui.readColorValue()),
            enabled: this.#enabled,
            interactiveToolApproval: this.#ui.interactiveToolApprovalToggle.checked,
            timezone,
            startLocal: readTrimmedInputValue(this.#ui.startInput),
            recurrence: readTrimmedSelectValue(this.#ui.recurrenceSelect),
            ...this.#limits.getSnapshotKey(),
            ...this.#modelSettings.getSnapshotKey(),
            ...this.#turns.getSnapshotKey()
        });
    }

    isValid(): boolean {
        if (this.#readOnly) {
            return true;
        }
        return this.#readValidatedPayload(false) !== null;
    }

    readAndValidate(): CreateAutomationPayload | null {
        if (this.#readOnly) {
            return null;
        }
        const payload = this.#readValidatedPayload(true);
        if (!payload) {
            return null;
        }
        this.#ui.hideError();
        return payload;
    }

    #readValidatedPayload(showErrors: boolean): CreateAutomationPayload | null {
        const title = readTrimmedInputValue(this.#ui.titleInput);
        if (!title) {
            if (showErrors) this.#ui.showError(i18n.t('automation.modal.validation.titleRequired'));
            return null;
        }

        const startLocal = readTrimmedInputValue(this.#ui.startInput);
        if (!startLocal) {
            if (showErrors) this.#ui.showError(i18n.t('automation.modal.validation.startRequired'));
            return null;
        }
        if (!parseStartLocalToDate(startLocal)) {
            if (showErrors) this.#ui.showError(i18n.t('automation.modal.validation.startInvalid'));
            return null;
        }

        const timezoneSelection = readTrimmedSelectValue(this.#ui.timezoneSelect);
        const timezone = timezoneSelection === 'auto' ? resolveBrowserTimezone() : timezoneSelection;
        if (!timezone) {
            if (showErrors) this.#ui.showError(i18n.t('automation.modal.validation.timezoneRequired'));
            return null;
        }

        const recurrence = resolveAutomationRecurrence(readTrimmedSelectValue(this.#ui.recurrenceSelect));
        if (!recurrence) {
            if (showErrors) this.#ui.showError(i18n.t('automation.modal.validation.recurrenceInvalid'));
            return null;
        }

        const limits = this.#limits.readAndValidate();
        if (!limits) {
            if (showErrors) this.#ui.showError(this.#limits.getValidationError() ?? i18n.t('automation.modal.validation.maxRunMinutesInvalid'));
            return null;
        }

        const modelSettingsError = this.#modelSettings.getValidationError();
        if (modelSettingsError) {
            if (showErrors) this.#ui.showError(modelSettingsError);
            return null;
        }

        const turns = this.#turns.readNormalizedTurns();
        if (!turns.length || turns.some((turn) => !turn)) {
            if (showErrors) this.#ui.showError(i18n.t('automation.modal.validation.turnsRequired'));
            return null;
        }
        if (turns.length > HARD_MAX_TURNS) {
            if (showErrors) this.#ui.showError(i18n.t('automation.modal.validation.tooManyTurns', { max: HARD_MAX_TURNS }));
            return null;
        }
        if (turns.some((turn) => turn.length > HARD_MAX_TURN_CHARS)) {
            if (showErrors) this.#ui.showError(i18n.t('automation.modal.validation.turnTooLong', { max: HARD_MAX_TURN_CHARS }));
            return null;
        }
        const maxTurnChars = Math.max(...turns.map((turn) => turn.length));

        const modelSettings = this.#modelSettings.readModelSettings();
        modelSettings.mcp.toolApprovalRequired = this.#ui.interactiveToolApprovalToggle.checked;
        return {
            title,
            color: normalizeAutomationColorSelection(this.#ui.readColorValue()),
            enabled: this.#enabled,
            timezone,
            startLocal: startLocal,
            recurrence,
            turns,
            maxTurns: turns.length,
            maxTurnChars: maxTurnChars,
            maxRunMinutes: limits.maxRunMinutes,
            interactiveToolApproval: this.#ui.interactiveToolApprovalToggle.checked,
            modelSettings: modelSettings
        };
    }

    #createDefaultMcpConfig(defaults: AutomationCreateDefaults): AutomationDefinition['modelSettings']['mcp'] {
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
