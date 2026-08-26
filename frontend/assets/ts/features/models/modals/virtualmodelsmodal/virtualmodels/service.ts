/* SoAI - Virtual model modal service [frontend/assets/ts/features/models/modals/virtualmodelsmodal/virtualmodels/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { VirtualModelsHost, VirtualModelsPrimaryTab, VirtualModelState } from '@features/models/modals/virtualmodelsmodal/virtualModelsManagerTypes.ts';

interface OpenVirtualModelsModalDependencies {
    host: VirtualModelsHost;
    state: VirtualModelState;
    modalId: string;
    valueControl(selector: string): HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;
    renderConstituentPicker(token: string, selectedIds?: string[]): void;
    bindVirtualModelSelectors(): void;
    updateVirtualTabControls(): void;
    updateVirtualTabs(active: VirtualModelsPrimaryTab): void;
    loadVirtualModelsList(): void;
    updateCreateAvailability(): void;
    notifyChanged(): void;
}

const openVirtualModelsModal = (dependencies: OpenVirtualModelsModalDependencies): void => {
    dependencies.state.virtualModelCount = 0;
    dependencies.state.virtualModelCache = [];
    dependencies.state.activeTab = 'create';
    dependencies.state.editModalOpen = false;
    dependencies.renderConstituentPicker('vm-models', []);
    dependencies.renderConstituentPicker('vm-edit-models', []);
    dependencies.bindVirtualModelSelectors();
    dependencies.updateVirtualTabControls();
    dependencies.updateVirtualTabs('create');
    dependencies.loadVirtualModelsList();
    dependencies.updateCreateAvailability();
    dependencies.state.originalCreateName = '';
    const strategyControl = dependencies.valueControl('vm-strategy');
    if (!(strategyControl instanceof HTMLSelectElement)) {
        throw new TypeError('Virtual model strategy control must be a select element');
    }
    const lastStrategy = dependencies.host.preferences.getLastVirtualModelStrategy();
    strategyControl.value = lastStrategy;
    dependencies.state.originalCreateStrategy = strategyControl.value;
    dependencies.state.originalCreateModels = [];
    dependencies.host.view.modals.open(dependencies.modalId);
    dependencies.notifyChanged();
};

export { openVirtualModelsModal };
export type { OpenVirtualModelsModalDependencies };
