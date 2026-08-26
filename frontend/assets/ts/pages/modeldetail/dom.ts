/* SoAI - Model detail page DOM contracts [frontend/assets/ts/pages/modeldetail/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { narrowButton, narrowSelect, optionalAnchor, optionalButton } from '@core/dom/narrowElement.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { MODEL_DETAIL_TEST_MODAL_ID } from '@features/modeldetail/public.ts';

export interface ModelDetailUi {
    root: HTMLElement;
    searchContainer: HTMLElement;
    saveParametersHeaderButton: HTMLButtonElement;
    resetAllParametersHeaderButton: HTMLButtonElement;
    manageAliasButton: HTMLButtonElement;
    testModelHeaderButton: HTMLButtonElement;
    switchToParametersButton: HTMLButtonElement;
    deleteModelButton: HTMLButtonElement;
    stopPluginButton: HTMLButtonElement | null;
    openAICapabilitiesSaveButton: HTMLButtonElement;

    modelTestModal: HTMLElement;
    backendDocButton: HTMLAnchorElement | null;

    parameterUnifiedFilter: HTMLSelectElement;
    modelTabsContainer: HTMLElement;
    overviewContent: HTMLElement;
    parametersContent: HTMLElement;
    parametersInterface: HTMLElement;
    modelDetailError: HTMLElement;
}

export const requireModelDetailUi = (dependencies: { requireHTMLElement: (selector: string, context?: ParentNode) => HTMLElement; optionalHTMLElement: (selector: string, context?: ParentNode) => HTMLElement | null }): ModelDetailUi => {
    const root = dependencies.requireHTMLElement('[data-section="modelDetail"]');
    const searchContainer = dependencies.requireHTMLElement('#modelDetail-search-container', root);

    const saveParametersHeaderButton = narrowButton(dependencies.requireHTMLElement('#save-params-header', root), 'Save parameters header');
    const resetAllParametersHeaderButton = narrowButton(dependencies.requireHTMLElement('#reset-all-params-header', root), 'Reset parameters header');
    const manageAliasButton = narrowButton(dependencies.requireHTMLElement('#manage-alias', root), 'Manage alias');
    const testModelHeaderButton = narrowButton(dependencies.requireHTMLElement('#test-model-header', root), 'Test model');
    const switchToParametersButton = narrowButton(dependencies.requireHTMLElement('#switch-to-parameters', root), 'Switch to parameters');
    const deleteModelButton = narrowButton(dependencies.requireHTMLElement('#delete-model', root), 'Delete model');
    const stopPluginButton = optionalButton(dependencies.optionalHTMLElement('#stop-plugin', root), 'Stop plugin');
    const openAICapabilitiesSaveButton = narrowButton(dependencies.requireHTMLElement('#modeldetail-openai-capabilities-save', root), 'OpenAI capabilities save');

    const modalPresenter = requireModalPresenter();
    const modelTestModal = modalPresenter.requireElement(MODEL_DETAIL_TEST_MODAL_ID);
    const backendDocButton = optionalAnchor(dependencies.optionalHTMLElement('#backend-doc-button', root), 'Backend doc');

    const parameterUnifiedFilter = narrowSelect(dependencies.requireHTMLElement('#param-unified-filter', root), 'Parameter unified filter');
    const modelTabsContainer = dependencies.requireHTMLElement('#model-tabs-container', root);
    const overviewContent = dependencies.requireHTMLElement('#overview-content', root);
    const parametersContent = dependencies.requireHTMLElement('#parameters-content', root);
    const parametersInterface = dependencies.requireHTMLElement('#parameters-interface', parametersContent);
    const modelDetailError = dependencies.requireHTMLElement('#model-detail-error', root);

    return {
        root,
        searchContainer,
        saveParametersHeaderButton,
        resetAllParametersHeaderButton,
        manageAliasButton,
        testModelHeaderButton,
        switchToParametersButton,
        deleteModelButton,
        stopPluginButton,
        openAICapabilitiesSaveButton,
        modelTestModal,
        backendDocButton,
        parameterUnifiedFilter,
        modelTabsContainer,
        overviewContent,
        parametersContent,
        parametersInterface,
        modelDetailError
    };
};

export const optionalModelDetailRoot = (dependencies: { optionalHTMLElement: (selector: string, context?: ParentNode) => HTMLElement | null }): HTMLElement | null => dependencies.optionalHTMLElement('[data-section="modelDetail"]');
