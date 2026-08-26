/* SoAI - Model editing modal field state [frontend/assets/ts/features/models/modals/editmodelmodal/fieldState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { FieldStateTracker } from '@core/forms/fieldStateTracker.ts';
import { dom } from '@core/dom/dom.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { MODELS_EDIT_MODEL_MODAL_ID } from '@features/models/modals/constants.ts';
import { hasEditModelEnabledChanges, type EditModelEnabledState } from '@features/models/modals/editmodelmodal/enabledControl.ts';

const EDIT_MODEL_ENABLED_FIELD_KEY = 'enabled';

const createEditModelFieldStateTracker = (modalRoot: HTMLElement): FieldStateTracker =>
    new FieldStateTracker({
        getElement: (key: string) => {
            if (key === EDIT_MODEL_ENABLED_FIELD_KEY) {
                return dom.resolve(modalUiSelector(MODELS_EDIT_MODEL_MODAL_ID, 'enabled-field'), modalRoot);
            }
            return null;
        }
    });

const syncEditModelFieldState = (tracker: FieldStateTracker | null, enabledState: EditModelEnabledState | null): void => {
    tracker?.setModified(EDIT_MODEL_ENABLED_FIELD_KEY, hasEditModelEnabledChanges(enabledState));
};

export { createEditModelFieldStateTracker, syncEditModelFieldState };
