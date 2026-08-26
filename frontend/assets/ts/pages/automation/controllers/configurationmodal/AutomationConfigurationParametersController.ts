/* SoAI - Automation configuration request parameters controller [frontend/assets/ts/pages/automation/controllers/configurationmodal/AutomationConfigurationParametersController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { openChatParameterEditorModal } from '@core/chat/parameters/parameterEditorModalSession.ts';
import { createChatParameterEditorProjection } from '@core/chat/parameters/parameterEditorState.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import { AUTOMATION_PARAMETERS_MODAL_ID, type AutomationDefinition } from '@features/automation/public.ts';
import { applyAutomationParametersStateToModelSettings, createDefaultAutomationParametersState, resolveAutomationParametersState, type AutomationParametersState } from '@pages/automation/controllers/configurationmodal/state.ts';

const AUTOMATION_CONFIGURATION_PARAMETERS_UPDATED_EVENT = 'automation:configuration:parameters-updated';

type ParametersControllerDependencies = {
    modalPresenter: ModalPresenterApi;
    resolveModelDetailId: () => string | null;
};

class AutomationConfigurationParametersController {
    readonly #dependencies: ParametersControllerDependencies;
    #state: AutomationParametersState = createDefaultAutomationParametersState();

    constructor(dependencies: ParametersControllerDependencies) {
        this.#dependencies = dependencies;
    }

    setValues(modelSettings: AutomationDefinition['modelSettings']): void {
        this.#state = resolveAutomationParametersState(modelSettings);
    }

    applyTo(settings: AutomationDefinition['modelSettings']): void {
        applyAutomationParametersStateToModelSettings(this.#state, settings);
    }

    getSummary(): string {
        return this.#state.hasExplicitParameters || this.#state.hasExplicitPrompts ? i18n.t('automation.modal.parameters.summaryCustom') : i18n.t('automation.modal.parameters.summaryDefault');
    }

    getProjection(): string {
        return createChatParameterEditorProjection(this.#state);
    }

    async openModal(readOnly: boolean, canApply: () => boolean): Promise<boolean> {
        if (readOnly) return false;
        const result = await openChatParameterEditorModal({
            presenter: this.#dependencies.modalPresenter,
            modalId: AUTOMATION_PARAMETERS_MODAL_ID,
            initialState: this.#state,
            includeSystemPromptLock: true,
            canApply,
            resolveModelDetailId: this.#dependencies.resolveModelDetailId,
            supportedReasoningLevels: null
        });
        if (!result || !canApply()) return false;
        this.#state = {
            parameters: result.parameters,
            prompts: {
                ...result.prompts,
                additionalPrompts: { ...this.#state.prompts.additionalPrompts }
            },
            hasExplicitParameters: true,
            hasExplicitPrompts: true
        };
        return true;
    }
}

export { AUTOMATION_CONFIGURATION_PARAMETERS_UPDATED_EVENT, AutomationConfigurationParametersController };
