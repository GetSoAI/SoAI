/* SoAI - Model renaming modal field state [frontend/assets/ts/features/models/modals/renamemodal/fieldState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readTrimmedInputValue } from '@core/dom/formValues.ts';
import { dom } from '@core/dom/dom.ts';
import { FieldStateTracker } from '@core/forms/fieldStateTracker.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { MODELS_RENAME_MODEL_MODAL_ID } from '@features/models/modals/constants.ts';

const RENAME_ALIAS_FIELD_KEY = 'alias';

const createRenameModelFieldStateTracker = (modalRoot: HTMLElement, aliasInput: HTMLInputElement, getOriginalAlias: () => string): FieldStateTracker =>
    new FieldStateTracker({
        getElement: (key: string) => (key === RENAME_ALIAS_FIELD_KEY ? dom.resolve(modalUiSelector(MODELS_RENAME_MODEL_MODAL_ID, 'alias-field'), modalRoot) : null),
        getCurrentValue: (key: string) => (key === RENAME_ALIAS_FIELD_KEY ? readTrimmedInputValue(aliasInput) : null),
        getOriginalValue: (key: string) => (key === RENAME_ALIAS_FIELD_KEY ? getOriginalAlias() : null)
    });

const syncRenameModelFieldState = (tracker: FieldStateTracker | null): void => {
    tracker?.update(RENAME_ALIAS_FIELD_KEY);
};

export { createRenameModelFieldStateTracker, syncRenameModelFieldState };
