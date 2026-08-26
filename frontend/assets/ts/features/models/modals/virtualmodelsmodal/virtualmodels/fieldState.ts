/* SoAI - Virtual model modal field state [frontend/assets/ts/features/models/modals/virtualmodelsmodal/virtualmodels/fieldState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readTrimmedInputValue } from '@core/dom/formValues.ts';
import { dom } from '@core/dom/dom.ts';
import { FieldStateTracker } from '@core/forms/fieldStateTracker.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { deepEqual } from '@core/primitives/equality.ts';
import { MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID, MODELS_VIRTUAL_MODELS_MODAL_ID } from '@features/models/modals/constants.ts';
import type { VirtualModelsHost, VirtualModelState } from '@features/models/modals/virtualmodelsmodal/virtualModelsManagerTypes.ts';

const CREATE_NAME_KEY = 'create.name';
const CREATE_STRATEGY_KEY = 'create.strategy';
const CREATE_MODELS_KEY = 'create.models';
const EDIT_STRATEGY_KEY = 'edit.strategy';
const EDIT_MODELS_KEY = 'edit.models';

type ValueControlResolver = (token: string) => HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;
type SelectionReader = (selector: string | Element, context?: Element) => { universalId: string }[];

const selectedIds = (records: { universalId: string }[]): string[] => records.map((record) => record.universalId);
const readInputControl = (control: HTMLInputElement | HTMLTextAreaElement): string => readTrimmedInputValue(control);

const createVirtualModelFieldStateTracker = (host: VirtualModelsHost, state: VirtualModelState, valueControl: ValueControlResolver, collectSelectedModels: SelectionReader): FieldStateTracker =>
    new FieldStateTracker({
        getElement: (key: string) => {
            const createRoot = host.view.modals.requireElement(MODELS_VIRTUAL_MODELS_MODAL_ID);
            const editRoot = host.view.modals.requireElement(MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID);
            if (key === CREATE_NAME_KEY) return dom.resolve(modalUiSelector(MODELS_VIRTUAL_MODELS_MODAL_ID, 'vm-name-field'), createRoot);
            if (key === CREATE_STRATEGY_KEY) return dom.resolve(modalUiSelector(MODELS_VIRTUAL_MODELS_MODAL_ID, 'vm-strategy-field'), createRoot);
            if (key === CREATE_MODELS_KEY) return dom.resolve(modalUiSelector(MODELS_VIRTUAL_MODELS_MODAL_ID, 'vm-models-field'), createRoot);
            if (key === EDIT_STRATEGY_KEY) return dom.resolve(modalUiSelector(MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID, 'vm-edit-strategy-field'), editRoot);
            if (key === EDIT_MODELS_KEY) return dom.resolve(modalUiSelector(MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID, 'vm-edit-models-field'), editRoot);
            return null;
        },
        getCurrentValue: (key: string) => {
            const createNameControl = valueControl('vm-name');
            if (key === CREATE_NAME_KEY) {
                if (!(createNameControl instanceof HTMLInputElement) && !(createNameControl instanceof HTMLTextAreaElement)) {
                    throw new TypeError('Virtual model name control must be an input or textarea element');
                }
                return readInputControl(createNameControl);
            }
            if (key === CREATE_STRATEGY_KEY) return valueControl('vm-strategy').value;
            if (key === CREATE_MODELS_KEY) return selectedIds(collectSelectedModels(modalUiSelector(MODELS_VIRTUAL_MODELS_MODAL_ID, 'vm-models'), host.view.modals.requireElement(MODELS_VIRTUAL_MODELS_MODAL_ID)));
            if (key === EDIT_STRATEGY_KEY) return valueControl('vm-edit-strategy').value;
            if (key === EDIT_MODELS_KEY) return selectedIds(collectSelectedModels(modalUiSelector(MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID, 'vm-edit-models'), host.view.modals.requireElement(MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID)));
            return null;
        },
        getOriginalValue: (key: string) => {
            if (key === CREATE_NAME_KEY) return state.originalCreateName;
            if (key === CREATE_STRATEGY_KEY) return state.originalCreateStrategy;
            if (key === CREATE_MODELS_KEY) return state.originalCreateModels;
            if (key === EDIT_STRATEGY_KEY) return state.originalEditStrategy;
            if (key === EDIT_MODELS_KEY) return state.originalEditModels;
            return null;
        },
        comparator: (current, original) => deepEqual(current, original)
    });

const syncVirtualModelFieldState = (tracker: FieldStateTracker | null, state: VirtualModelState): void => {
    tracker?.refresh([CREATE_NAME_KEY, CREATE_STRATEGY_KEY, CREATE_MODELS_KEY]);
    if (state.editModalOpen) {
        tracker?.refresh([EDIT_STRATEGY_KEY, EDIT_MODELS_KEY]);
    } else {
        tracker?.clear(EDIT_STRATEGY_KEY);
        tracker?.clear(EDIT_MODELS_KEY);
    }
};

export { createVirtualModelFieldStateTracker, syncVirtualModelFieldState };
