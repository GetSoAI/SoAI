/* SoAI - Model detail page control layer action handlers [frontend/assets/ts/pages/modeldetail/controllers/modelDetailActionHandlers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ACTION_BACKEND_DOCUMENTATION, ACTION_BACK_TO_MODELS, ACTION_DELETE_MODEL, ACTION_EDIT_VIRTUAL_MODEL, ACTION_MANAGE_ALIAS, ACTION_PARAMETER_TEMPLATE_ADD_ARRAY_ITEM, ACTION_PARAMETER_TEMPLATE_REMOVE_ARRAY_ITEM, ACTION_RESET_ALL_PARAMETERS, ACTION_RESET_OPENAI_CAPABILITIES, ACTION_SAVE_PARAMETERS, ACTION_STOP_PLUGIN, ACTION_SWITCH_TO_PARAMETERS, ACTION_TEST_COPY_LOGS, ACTION_TEST_LONG, ACTION_TEST_MODEL, ACTION_TEST_RESET, ACTION_TEST_SHORT, ACTION_TEST_STOP_PLUGIN, ACTION_TEST_TOGGLE_LOGS, ACTION_TOGGLE_MODEL_ENABLED, ACTION_TOGGLE_OPENAI_CAPABILITY, type ActionHandlerMap } from '@features/modeldetail/public.ts';

interface ModelDetailNavigationActions {
    goBackToModels(): void;
    switchToParameters(): void;
    openBackendDocumentation(): void;
}

interface ModelDetailModelActions {
    saveParameters(): void;
    resetAllParameters(): void;
    manageAlias(): void;
    openTestModal(): void;
    editVirtualModel(): void;
    deleteModel(): void;
    stopPlugin(): void;
    toggleModelEnabled(event: Event, element: HTMLElement): void;
}

interface ModelDetailTestActions {
    startShortTest(): void;
    startLongTest(): void;
    stopPluginFromTest(): void;
    resetTest(): void;
    copyTestLogs(): void;
    toggleTestLogs(): void;
}

interface ModelDetailCapabilityActions {
    toggleOpenAICapability(event: Event, element: HTMLElement): void;
    resetOpenAICapabilities(): void;
}

interface ModelDetailParameterActions {
    addParameterArrayItem(element: HTMLElement): void;
    removeParameterArrayItem(element: HTMLElement): void;
}

interface ModelDetailActionHandlersHost {
    navigation: ModelDetailNavigationActions;
    model: ModelDetailModelActions;
    test: ModelDetailTestActions;
    capabilities: ModelDetailCapabilityActions;
    parameters: ModelDetailParameterActions;
}

const createModelDetailActionHandlers = (host: ModelDetailActionHandlersHost): ActionHandlerMap => {
    return {
        [ACTION_BACK_TO_MODELS]: () => host.navigation.goBackToModels(),
        [ACTION_SAVE_PARAMETERS]: () => host.model.saveParameters(),
        [ACTION_RESET_ALL_PARAMETERS]: () => host.model.resetAllParameters(),
        [ACTION_MANAGE_ALIAS]: () => host.model.manageAlias(),
        [ACTION_TEST_MODEL]: () => host.model.openTestModal(),
        [ACTION_SWITCH_TO_PARAMETERS]: () => host.navigation.switchToParameters(),
        [ACTION_EDIT_VIRTUAL_MODEL]: () => host.model.editVirtualModel(),
        [ACTION_DELETE_MODEL]: () => host.model.deleteModel(),
        [ACTION_STOP_PLUGIN]: () => host.model.stopPlugin(),
        [ACTION_TEST_SHORT]: () => host.test.startShortTest(),
        [ACTION_TEST_LONG]: () => host.test.startLongTest(),
        [ACTION_TEST_STOP_PLUGIN]: () => host.test.stopPluginFromTest(),
        [ACTION_TEST_RESET]: () => host.test.resetTest(),
        [ACTION_TEST_COPY_LOGS]: () => host.test.copyTestLogs(),
        [ACTION_TEST_TOGGLE_LOGS]: () => host.test.toggleTestLogs(),
        [ACTION_BACKEND_DOCUMENTATION]: () => host.navigation.openBackendDocumentation(),
        [ACTION_TOGGLE_MODEL_ENABLED]: (event: Event, element: HTMLElement) => host.model.toggleModelEnabled(event, element),
        [ACTION_TOGGLE_OPENAI_CAPABILITY]: (event: Event, element: HTMLElement) => host.capabilities.toggleOpenAICapability(event, element),
        [ACTION_RESET_OPENAI_CAPABILITIES]: () => host.capabilities.resetOpenAICapabilities(),
        [ACTION_PARAMETER_TEMPLATE_ADD_ARRAY_ITEM]: (_event: Event, element: HTMLElement) => host.parameters.addParameterArrayItem(element),
        [ACTION_PARAMETER_TEMPLATE_REMOVE_ARRAY_ITEM]: (_event: Event, element: HTMLElement) => host.parameters.removeParameterArrayItem(element)
    };
};

export { createModelDetailActionHandlers };
export type { ModelDetailActionHandlersHost };
