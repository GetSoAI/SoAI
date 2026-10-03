/* SoAI - Model detail action identifiers [frontend/assets/ts/features/modeldetail/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';

export const ACTION_BACK_TO_MODELS = 'back-to-models';
export const ACTION_SAVE_PARAMETERS = 'save-parameters';
export const ACTION_RESET_ALL_PARAMETERS = 'reset-all-parameters';
export const ACTION_MANAGE_ALIAS = 'manage-alias';
export const ACTION_TEST_MODEL = 'test-model';
export const ACTION_EDIT_VIRTUAL_MODEL = 'edit-virtual-model';
export const ACTION_DELETE_MODEL = 'delete-model';
export const ACTION_STOP_PLUGIN = 'stop-plugin';
export const ACTION_TEST_SHORT = 'test-short';
export const ACTION_TEST_LONG = 'test-long';
export const ACTION_TEST_STOP_PLUGIN = 'test-stop-plugin';
export const ACTION_TEST_RESET = 'test-reset';
export const ACTION_TEST_COPY_LOGS = 'test-copy-logs';
export const ACTION_TEST_TOGGLE_LOGS = 'test-toggle-logs';
export const ACTION_BACKEND_DOCUMENTATION = 'backend-documentation';
export const ACTION_TOGGLE_MODEL_ENABLED = 'toggle-model-enabled';
export const ACTION_TOGGLE_OPENAI_CAPABILITY = 'toggle-openai-capability';
export const ACTION_RESET_OPENAI_CAPABILITIES = 'reset-openai-capabilities';
export const ACTION_PARAMETER_TEMPLATE_ADD_ARRAY_ITEM = 'parameter-template-add-array-item';
export const ACTION_PARAMETER_TEMPLATE_REMOVE_ARRAY_ITEM = 'parameter-template-remove-array-item';
export const ACTION_PARAMETER_REVERT = 'parameter-revert';
export const ACTION_PARAMETER_SELECT_VIEW = 'parameter-select-view';
export const ACTION_PARAMETER_SELECT_GROUP = 'parameter-select-group';
export const ACTION_PARAMETER_NAVIGATE_CATEGORY = 'parameter-navigate-category';
export const ACTION_COPY_MODEL_DETAIL_VALUE = 'copy-model-detail-value';

export type ModeldetailActionId = typeof ACTION_BACK_TO_MODELS | typeof ACTION_SAVE_PARAMETERS | typeof ACTION_RESET_ALL_PARAMETERS | typeof ACTION_MANAGE_ALIAS | typeof ACTION_TEST_MODEL | typeof ACTION_EDIT_VIRTUAL_MODEL | typeof ACTION_DELETE_MODEL | typeof ACTION_STOP_PLUGIN | typeof ACTION_TEST_SHORT | typeof ACTION_TEST_LONG | typeof ACTION_TEST_STOP_PLUGIN | typeof ACTION_TEST_RESET | typeof ACTION_TEST_COPY_LOGS | typeof ACTION_TEST_TOGGLE_LOGS | typeof ACTION_BACKEND_DOCUMENTATION | typeof ACTION_TOGGLE_MODEL_ENABLED | typeof ACTION_TOGGLE_OPENAI_CAPABILITY | typeof ACTION_RESET_OPENAI_CAPABILITIES | typeof ACTION_PARAMETER_TEMPLATE_ADD_ARRAY_ITEM | typeof ACTION_PARAMETER_TEMPLATE_REMOVE_ARRAY_ITEM | typeof ACTION_PARAMETER_REVERT | typeof ACTION_PARAMETER_SELECT_VIEW | typeof ACTION_PARAMETER_SELECT_GROUP | typeof ACTION_PARAMETER_NAVIGATE_CATEGORY | typeof ACTION_COPY_MODEL_DETAIL_VALUE;

const { guard: isModeldetailActionId } = createActionIdSet(ACTION_BACK_TO_MODELS, ACTION_SAVE_PARAMETERS, ACTION_RESET_ALL_PARAMETERS, ACTION_MANAGE_ALIAS, ACTION_TEST_MODEL, ACTION_EDIT_VIRTUAL_MODEL, ACTION_DELETE_MODEL, ACTION_STOP_PLUGIN, ACTION_TEST_SHORT, ACTION_TEST_LONG, ACTION_TEST_STOP_PLUGIN, ACTION_TEST_RESET, ACTION_TEST_COPY_LOGS, ACTION_TEST_TOGGLE_LOGS, ACTION_BACKEND_DOCUMENTATION, ACTION_TOGGLE_MODEL_ENABLED, ACTION_TOGGLE_OPENAI_CAPABILITY, ACTION_RESET_OPENAI_CAPABILITIES, ACTION_PARAMETER_TEMPLATE_ADD_ARRAY_ITEM, ACTION_PARAMETER_TEMPLATE_REMOVE_ARRAY_ITEM, ACTION_PARAMETER_REVERT, ACTION_PARAMETER_SELECT_VIEW, ACTION_PARAMETER_SELECT_GROUP, ACTION_PARAMETER_NAVIGATE_CATEGORY, ACTION_COPY_MODEL_DETAIL_VALUE);

export { isModeldetailActionId };

interface ActionHandler {
    (event: Event, element: HTMLElement): void;
}

type ActionHandlerMap = Record<ModeldetailActionId, ActionHandler>;

export type { ActionHandler, ActionHandlerMap };
