/* SoAI - Virtual models save wiring [frontend/assets/ts/features/models/modals/virtualmodelsmodal/virtualmodelsmanager/saveController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { modalUiSelector } from '@core/modals/uiIds.ts';
import { createSaveController, SAVE_HEADER_PRIORITY_MODAL, type SaveController } from '@core/save/public.ts';
import { setAriaBusy } from '@core/ui/controls/ariaBusy.ts';
import type { VirtualModelsHost } from '@features/models/modals/virtualmodelsmodal/virtualModelsManagerTypes.ts';

type VirtualModelsSaveWiringDependencies = {
    host: VirtualModelsHost;
    modalId: string;
    editModalId: string;
    hasCreateChanges(): boolean;
    hasEditChanges(): boolean;
    isCreateValid(): boolean;
    isEditValid(): boolean;
    saveCreate(): Promise<void>;
    saveEdit(): Promise<void>;
};

const createVirtualModelsSaveController = (dependencies: VirtualModelsSaveWiringDependencies): SaveController => {
    const saveController = createSaveController({
        headerContextId: 'virtual-models',
        headerPriority: SAVE_HEADER_PRIORITY_MODAL,
        requestContextLabel: 'Virtual models save',
        units: [
            {
                id: 'virtual-models-create',
                hasChanges: () => dependencies.hasCreateChanges(),
                isValid: () => dependencies.isCreateValid(),
                save: () => dependencies.saveCreate()
            },
            {
                id: 'virtual-models-edit',
                hasChanges: () => dependencies.hasEditChanges(),
                isValid: () => dependencies.isEditValid(),
                save: () => dependencies.saveEdit()
            }
        ]
    });

    const modalRoot = dependencies.host.view.modals.requireElement(dependencies.modalId);
    const editModalRoot = dependencies.host.view.modals.requireElement(dependencies.editModalId);
    setAriaBusy(modalRoot, false);
    setAriaBusy(editModalRoot, false);

    const notifyRoot = modalRoot.parentElement instanceof HTMLElement ? modalRoot.parentElement : modalRoot;
    saveController.attach({
        resolveSaveButtons: (): readonly HTMLButtonElement[] => {
            const createButton = dependencies.host.view.requireHTMLElement(modalUiSelector(dependencies.modalId, 'vm-save-create'), modalRoot);
            const editButton = dependencies.host.view.requireHTMLElement(modalUiSelector(dependencies.editModalId, 'vm-save-edit'), editModalRoot);
            if (!(createButton instanceof HTMLButtonElement) || !(editButton instanceof HTMLButtonElement)) {
                throw new TypeError('Virtual models save controls must be button elements');
            }
            return [createButton, editButton];
        },
        busyRoots: [modalRoot, editModalRoot],
        autoNotifyRoot: notifyRoot
    });

    return saveController;
};

export { createVirtualModelsSaveController };
export type { VirtualModelsSaveWiringDependencies };
