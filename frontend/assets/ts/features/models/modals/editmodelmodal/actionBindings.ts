/* SoAI - Model editing modal action bindings [frontend/assets/ts/features/models/modals/editmodelmodal/actionBindings.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { bindDataActionListener } from '@core/dom/dataActionBinding.ts';
import { EDIT_MODEL_MODAL_ACTION_COPY_SOURCE, EDIT_MODEL_MODAL_ACTION_DELETE, EDIT_MODEL_MODAL_ACTION_EDIT_PARAMETERS, EDIT_MODEL_MODAL_ACTION_RENAME, EDIT_MODEL_MODAL_ACTION_SAVE, EDIT_MODEL_MODAL_ACTION_TEST_MODEL, EDIT_MODEL_MODAL_ACTION_TOGGLE_ENABLED, EDIT_MODEL_MODAL_ACTION_TOGGLE_OPENAI_CAPABILITY, EDIT_MODEL_MODAL_ACTION_VIEW_INFO, isEditModelModalChangeActionId, isEditModelModalClickActionId, type EditModelModalChangeActionId, type EditModelModalClickActionId } from '@features/models/modals/constants.ts';

interface EditModelModalActionBindingOptions {
    root: HTMLElement;
    signal: AbortSignal;
    onCopySource: () => void;
    onViewInfo: () => void;
    onTestModel: () => void;
    onEditParameters: () => void;
    onRename: () => void;
    onDelete: () => void;
    onSave: () => void;
    onEnabledChange: (actionElement: HTMLElement) => void;
    onCapabilityChange: (actionElement: HTMLElement) => void;
}

const handleEditModelModalClickAction = (action: EditModelModalClickActionId, options: EditModelModalActionBindingOptions): void => {
    if (action === EDIT_MODEL_MODAL_ACTION_COPY_SOURCE) {
        options.onCopySource();
        return;
    }
    if (action === EDIT_MODEL_MODAL_ACTION_VIEW_INFO) {
        options.onViewInfo();
        return;
    }
    if (action === EDIT_MODEL_MODAL_ACTION_TEST_MODEL) {
        options.onTestModel();
        return;
    }
    if (action === EDIT_MODEL_MODAL_ACTION_EDIT_PARAMETERS) {
        options.onEditParameters();
        return;
    }
    if (action === EDIT_MODEL_MODAL_ACTION_RENAME) {
        options.onRename();
        return;
    }
    if (action === EDIT_MODEL_MODAL_ACTION_DELETE) {
        options.onDelete();
        return;
    }
    if (action === EDIT_MODEL_MODAL_ACTION_SAVE) {
        options.onSave();
    }
};

const handleEditModelModalChangeAction = (action: EditModelModalChangeActionId, actionElement: HTMLElement, options: EditModelModalActionBindingOptions): void => {
    if (action === EDIT_MODEL_MODAL_ACTION_TOGGLE_ENABLED) {
        options.onEnabledChange(actionElement);
        return;
    }
    if (action === EDIT_MODEL_MODAL_ACTION_TOGGLE_OPENAI_CAPABILITY) {
        options.onCapabilityChange(actionElement);
    }
};

const bindEditModelModalActions = (options: EditModelModalActionBindingOptions): void => {
    bindDataActionListener({
        root: options.root,
        eventType: 'click',
        signal: options.signal,
        isAction: isEditModelModalClickActionId,
        mouseButton: 'primary',
        preventDefault: 'interactive',
        onAction: ({ action }): void => handleEditModelModalClickAction(action, options)
    });
    bindDataActionListener({
        root: options.root,
        eventType: 'change',
        signal: options.signal,
        isAction: isEditModelModalChangeActionId,
        preventDefault: 'never',
        onAction: ({ action, actionElement }): void => handleEditModelModalChangeAction(action, actionElement, options)
    });
};

export { bindEditModelModalActions };
