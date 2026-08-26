/* SoAI - Virtual model modal action bindings [frontend/assets/ts/features/models/modals/virtualmodelsmodal/virtualmodels/actionBindings.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { bindDataActionListener } from '@core/dom/dataActionBinding.ts';
import { VIRTUAL_MODELS_MODAL_ACTION_CREATE_TAB, VIRTUAL_MODELS_MODAL_ACTION_DELETE, VIRTUAL_MODELS_MODAL_ACTION_EDIT, VIRTUAL_MODELS_MODAL_ACTION_LIST_TAB, isVirtualModelsModalClickActionId, type VirtualModelsModalClickActionId } from '@features/models/modals/constants.ts';

interface VirtualModelsModalActionBindingOptions {
    root: HTMLElement;
    signal: AbortSignal;
    showCreateVirtualModelForm(): void;
    showVirtualModelsListSection(): void;
    showEditVirtualModelForm(name: string): Promise<void>;
    deleteVirtualModel(name: string): Promise<void>;
}

const requireVirtualModelName = (actionElement: HTMLElement): string => {
    const name = actionElement.dataset['vmName'];
    if (!name) {
        throw new Error('Virtual models modal action requires data-vm-name');
    }
    return name;
};

const handleVirtualModelsModalClickAction = (action: VirtualModelsModalClickActionId, actionElement: HTMLElement, options: VirtualModelsModalActionBindingOptions): void | Promise<void> => {
    if (action === VIRTUAL_MODELS_MODAL_ACTION_CREATE_TAB) {
        options.showCreateVirtualModelForm();
        return;
    }
    if (action === VIRTUAL_MODELS_MODAL_ACTION_LIST_TAB) {
        return options.showVirtualModelsListSection();
    }
    if (action === VIRTUAL_MODELS_MODAL_ACTION_EDIT) {
        return options.showEditVirtualModelForm(requireVirtualModelName(actionElement));
    }
    if (action === VIRTUAL_MODELS_MODAL_ACTION_DELETE) {
        return options.deleteVirtualModel(requireVirtualModelName(actionElement));
    }
};

const bindVirtualModelsModalActions = (options: VirtualModelsModalActionBindingOptions): void => {
    bindDataActionListener({
        root: options.root,
        eventType: 'click',
        signal: options.signal,
        isAction: isVirtualModelsModalClickActionId,
        mouseButton: 'primary',
        preventDefault: 'interactive',
        stopPropagation: true,
        onAction: ({ action, actionElement }): void | Promise<void> => handleVirtualModelsModalClickAction(action, actionElement, options)
    });
};

export { bindVirtualModelsModalActions };
export type { VirtualModelsModalActionBindingOptions };
