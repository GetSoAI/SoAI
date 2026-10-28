/* SoAI - Automation page configuration model settings controller [frontend/assets/ts/pages/automation/controllers/configurationmodal/AutomationConfigurationModelSettingsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readTrimmedSelectValue } from '@core/dom/formValues.ts';
import { replaceSelectOptions, type SelectEntryDefinition, type SelectOptionDefinition, type SelectOptionGroupDefinition } from '@core/dom/selectOptions.ts';
import { setSelectValueAndSyncDefault } from '@core/dom/selectSelection.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { capitalize } from '@core/primitives/text.ts';
import { cloneStructured } from '@core/primitives/clone.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { ReadOnlyFileBrowserApi } from '@core/fileexplorerbrowser/types.ts';
import { WorkspacePathDraft } from '@core/fileexplorerbrowser/workspacePathDraft.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import { McpFormController } from '@core/mcp/mcpFormController.ts';
import { AUTOMATION_ACTION_MCP_SERVER_TOGGLE, AUTOMATION_ACTION_MCP_TOOL_GROUP_TOGGLE, AUTOMATION_ACTION_MCP_TOOL_SEARCH, AUTOMATION_ACTION_MCP_TOOL_TOGGLE, AUTOMATION_ACTION_MCP_TOOL_MODE_SELECT, AUTOMATION_CONFIGURATION_MODAL_ID, requireAutomationMcpToolsEmpty, requireAutomationMcpToolsList, type AutomationDefinitionResponse, type AutomationMcpCatalogResponse, type AutomationModelOption } from '@features/automation/public.ts';
import { AUTOMATION_CONFIGURATION_PARAMETERS_UPDATED_EVENT, AutomationConfigurationParametersController } from '@pages/automation/controllers/configurationmodal/AutomationConfigurationParametersController.ts';

interface ModelSettingsUi {
    modalRoot: HTMLElement;
    modelSelect: HTMLSelectElement;
    workspacePathInput: HTMLInputElement;
    parametersSummaryInput: HTMLInputElement;
    modalPresenter: ModalPresenterApi;
    getIconSync: (icon: IconName, options?: IconOptions) => TrustedHtml;
}

const AUTOMATION_CONFIGURATION_WORKSPACE_UPDATED_EVENT = 'automation:configuration:workspace-updated';
const AUTOMATION_CONFIGURATION_MCP_UPDATED_EVENT = 'automation:configuration:mcp-updated';

class AutomationConfigurationModelSettingsController {
    readonly #ui: ModelSettingsUi;
    readonly #mcp: McpFormController;
    readonly #parameters: AutomationConfigurationParametersController;
    readonly #workspace: WorkspacePathDraft;
    #availableModels: readonly AutomationModelOption[] = [];
    #storedSettings: AutomationDefinitionResponse['modelSettings'] | null = null;
    #readOnly = false;

    constructor(ui: ModelSettingsUi) {
        this.#ui = ui;
        this.#mcp = new McpFormController({
            root: ui.modalRoot,
            toolsList: requireAutomationMcpToolsList(ui.modalRoot),
            toolsEmpty: requireAutomationMcpToolsEmpty(ui.modalRoot),
            modalId: AUTOMATION_CONFIGURATION_MODAL_ID,
            actions: {
                serverToggle: AUTOMATION_ACTION_MCP_SERVER_TOGGLE,
                toolToggle: AUTOMATION_ACTION_MCP_TOOL_TOGGLE,
                toolModeSelect: AUTOMATION_ACTION_MCP_TOOL_MODE_SELECT,
                toolGroupToggle: AUTOMATION_ACTION_MCP_TOOL_GROUP_TOGGLE,
                toolSearch: AUTOMATION_ACTION_MCP_TOOL_SEARCH
            },
            toolModes: ['execute'],
            initialToolMode: 'execute',
            getIconSync: ui.getIconSync,
            onConfigurationChanged: () => {
                this.#ui.modalRoot.dispatchEvent(new CustomEvent(AUTOMATION_CONFIGURATION_MCP_UPDATED_EVENT, { bubbles: true }));
            }
        });
        this.#parameters = new AutomationConfigurationParametersController({
            modalPresenter: ui.modalPresenter,
            resolveModelDetailId: () => this.#resolveModelOption(readTrimmedSelectValue(this.#ui.modelSelect))?.detailUniversalId ?? null
        });
        this.#workspace = new WorkspacePathDraft();
    }

    setAvailableModels(models: readonly AutomationModelOption[]): void {
        this.#availableModels = models;
        this.#renderModelOptions(readTrimmedSelectValue(this.#ui.modelSelect));
    }

    setMcpCatalog(catalog: AutomationMcpCatalogResponse): void {
        this.#mcp.setCatalog(catalog);
    }

    setValues(modelSettings: AutomationDefinitionResponse['modelSettings'], currentWorkspacePath: string): void {
        this.#storedSettings = cloneStructured(modelSettings);
        const model = toTrimmedString(modelSettings.model) || this.#resolveDefaultModel();
        this.#renderModelOptions(model);
        setSelectValueAndSyncDefault(this.#ui.modelSelect, model);
        this.#mcp.setValues(modelSettings.mcp);
        this.#parameters.setValues(modelSettings);
        this.#workspace.setValue(modelSettings.workspacePath, currentWorkspacePath);
        this.#syncSummaries();
    }

    setReadOnly(readOnly: boolean): void {
        this.#readOnly = readOnly;
        this.#mcp.setReadOnly(readOnly);
    }

    destroy(): void {
        this.#mcp.destroy();
    }

    async openWorkspaceModal(api: ReadOnlyFileBrowserApi, canApply: () => boolean, signal?: AbortSignal): Promise<boolean> {
        if (
            await this.#workspace.open({
                access: {
                    currentWorkspacePath: this.#workspace.getCurrentWorkspacePath(),
                    browserApi: api
                },
                readOnly: this.#readOnly,
                canApply,
                signal,
                strings: {
                    title: i18n.t('automation.modal.workspace.title'),
                    message: i18n.t('automation.modal.workspace.description'),
                    chooseCurrent: i18n.t('common.save')
                }
            })
        ) {
            this.#syncSummaries();
            this.#ui.modalRoot.dispatchEvent(new CustomEvent(AUTOMATION_CONFIGURATION_WORKSPACE_UPDATED_EVENT, { bubbles: true }));
            return true;
        }
        return false;
    }

    async openParametersModal(canApply: () => boolean, signal?: AbortSignal): Promise<boolean> {
        if (await this.#parameters.openModal(this.#readOnly, canApply, signal)) {
            this.#syncSummaries();
            this.#ui.modalRoot.dispatchEvent(new CustomEvent(AUTOMATION_CONFIGURATION_PARAMETERS_UPDATED_EVENT, { bubbles: true }));
            return true;
        }
        return false;
    }

    #resolveModelOption(modelId: string): AutomationModelOption | null {
        const trimmed = toTrimmedString(modelId);
        if (!trimmed) {
            return null;
        }
        return this.#availableModels.find((model) => model.id === trimmed) ?? null;
    }

    #isModelSelectable(option: AutomationModelOption): boolean {
        return option.ineligibleReason === null;
    }

    getModelIssue(): string | null {
        const model = readTrimmedSelectValue(this.#ui.modelSelect);
        if (!model) {
            return i18n.t('automation.modal.validation.modelRequired');
        }
        const option = this.#resolveModelOption(model);
        if (!option) {
            return i18n.t('automation.modal.validation.modelMissing', { model });
        }
        if (option.ineligibleReason === 'disabled') {
            return i18n.t('automation.modal.validation.modelDisabled', { model: option.label });
        }
        if (option.ineligibleReason === 'unavailable') {
            return i18n.t('automation.modal.validation.modelUnavailable', { model: option.label });
        }
        if (option.ineligibleReason === 'unsupported') {
            return i18n.t('automation.modal.validation.modelUnsupported', { model: option.label });
        }
        return null;
    }

    readModelSettings(): AutomationDefinitionResponse['modelSettings'] {
        const model = readTrimmedSelectValue(this.#ui.modelSelect);
        const settings: AutomationDefinitionResponse['modelSettings'] = {
            ...cloneStructured(this.#storedSettings),
            model,
            agent: { ...this.#storedSettings?.agent, mode: 'execute' },
            mcp: { ...cloneStructured(this.#storedSettings?.mcp), ...this.#mcp.readConfig() }
        };
        this.#parameters.applyTo(settings);
        const workspacePath = this.#workspace.getValue();
        if (workspacePath !== null) settings.workspacePath = workspacePath;
        return settings;
    }

    #syncSummaries(): void {
        this.#ui.workspacePathInput.value = this.#workspace.getSummary();
        this.#ui.parametersSummaryInput.value = this.#parameters.getSummary();
        this.#ui.parametersSummaryInput.dataset['parametersProjection'] = this.#parameters.getProjection();
    }

    #resolveDefaultModel(): string {
        const first = this.#availableModels.find((model) => this.#isModelSelectable(model));
        return first ? first.id : '';
    }

    #renderModelOptions(selectedModel: string): void {
        const select = this.#ui.modelSelect;
        const placeholderOption: SelectOptionDefinition = {
            value: '',
            label: i18n.t('automation.modal.placeholders.model')
        };
        const modelsByProvider = new Map<string, AutomationModelOption[]>();
        this.#availableModels.forEach((model) => {
            const provider = toTrimmedString(model.provider) || 'default';
            const bucket = modelsByProvider.get(provider);
            if (bucket) {
                bucket.push(model);
                return;
            }
            modelsByProvider.set(provider, [model]);
        });
        const createOption = (model: AutomationModelOption): SelectOptionDefinition => ({
            value: model.id,
            label: toTrimmedString(`${model.label} ${this.#formatStatus(model)}`),
            selected: model.id === selectedModel,
            disabled: !this.#isModelSelectable(model)
        });
        const entries: SelectEntryDefinition[] =
            modelsByProvider.size > 1
                ? Array.from(modelsByProvider.entries()).map(([provider, models]): SelectOptionGroupDefinition => ({
                      label: capitalize(provider),
                      options: models.map((model) => createOption(model))
                  }))
                : this.#availableModels.map((model) => createOption(model));
        replaceSelectOptions(select, selectedModel ? entries : [placeholderOption, ...entries]);
        const normalizedSelectedModel = toTrimmedString(selectedModel);
        if (normalizedSelectedModel && !this.#availableModels.some((model) => model.id === normalizedSelectedModel)) {
            const option = document.createElement('option');
            option.value = normalizedSelectedModel;
            option.textContent = i18n.t('automation.modal.unavailableModelOption', { model: normalizedSelectedModel });
            option.disabled = true;
            select.append(option);
        }
        if (!normalizedSelectedModel) {
            setSelectValueAndSyncDefault(select, this.#resolveDefaultModel());
            return;
        }
        setSelectValueAndSyncDefault(select, normalizedSelectedModel);
    }

    #formatStatus(model: AutomationModelOption): string {
        if (model.ineligibleReason === 'disabled') {
            return i18n.t('common.disabled');
        }
        if (model.ineligibleReason === 'unavailable') {
            return i18n.t('automation.modal.modelStatus.unavailable');
        }
        if (model.ineligibleReason === 'unsupported') {
            return i18n.t('automation.modal.modelStatus.unsupported');
        }
        return model.loaded ? i18n.t('chat.models.loaded') : i18n.t('chat.models.available');
    }
}

export { AUTOMATION_CONFIGURATION_MCP_UPDATED_EVENT, AUTOMATION_CONFIGURATION_WORKSPACE_UPDATED_EVENT, AutomationConfigurationModelSettingsController };
