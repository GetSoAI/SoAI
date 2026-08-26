/* SoAI - Model detail feature public surface [frontend/assets/ts/features/modeldetail/public.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export { MODEL_DETAIL_TEST_MODAL_ID } from '@features/modeldetail/modals/constants.ts';
export { TestModalManager } from '@features/modeldetail/modals/TestModalManager.ts';
export type { TestModalLogEntry, TestModalLogStreamHandle, TestModalManagerHost, TestModalManagerOptions, TestModalNotificationType, TestModalRequestState, TestModalRequestStatus, TestRunMode, TestModalState, TestModalStatusPresenter, TestModalStreamRequest } from '@features/modeldetail/modals/TestModalManagerTypes.ts';
export { ACTION_BACKEND_DOCUMENTATION, ACTION_BACK_TO_MODELS, ACTION_DELETE_MODEL, ACTION_EDIT_VIRTUAL_MODEL, ACTION_MANAGE_ALIAS, ACTION_PARAMETER_TEMPLATE_ADD_ARRAY_ITEM, ACTION_PARAMETER_TEMPLATE_REMOVE_ARRAY_ITEM, ACTION_RESET_ALL_PARAMETERS, ACTION_RESET_OPENAI_CAPABILITIES, ACTION_SAVE_PARAMETERS, ACTION_STOP_PLUGIN, ACTION_SWITCH_TO_PARAMETERS, ACTION_TEST_COPY_LOGS, ACTION_TEST_LONG, ACTION_TEST_MODEL, ACTION_TEST_RESET, ACTION_TEST_SHORT, ACTION_TEST_STOP_PLUGIN, ACTION_TEST_TOGGLE_LOGS, ACTION_TOGGLE_MODEL_ENABLED, ACTION_TOGGLE_OPENAI_CAPABILITY, isModeldetailActionId } from '@features/modeldetail/actions.ts';
export type { ActionHandler, ActionHandlerMap, ModeldetailActionId } from '@features/modeldetail/actions.ts';
