/* SoAI - Messaging settings action and modal constants [frontend/assets/ts/features/settings/messaging/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';

const SETTINGS_MESSAGING_ACCOUNT_MODAL_ID = 'settings-messaging-account-modal';
const SETTINGS_MESSAGING_PARAMETERS_MODAL_ID = 'settings-messaging-parameters-modal';
const MESSAGING_ACTION_ADD_ACCOUNT = 'settings.messaging.addAccount';
const MESSAGING_ACTION_EDIT_ACCOUNT = 'settings.messaging.editAccount';
const MESSAGING_ACTION_ENABLE_ACCOUNT = 'settings.messaging.enableAccount';
const MESSAGING_ACTION_DISABLE_ACCOUNT = 'settings.messaging.disableAccount';
const MESSAGING_ACTION_REMOVE_ACCOUNT = 'settings.messaging.removeAccount';

const MESSAGING_MODAL_ACTION_SAVE = 'settings.messaging.modal.save';
const MESSAGING_MODAL_ACTION_WORKSPACE = 'settings.messaging.modal.workspace';
const MESSAGING_MODAL_ACTION_PARAMETERS = 'settings.messaging.modal.parameters';
const MESSAGING_MODAL_ACTION_MCP_SERVER_TOGGLE = 'settings.messaging.modal.mcpServerToggle';
const MESSAGING_MODAL_ACTION_MCP_TOOL_TOGGLE = 'settings.messaging.modal.mcpToolToggle';
const MESSAGING_MODAL_ACTION_MCP_MODE_SELECT = 'settings.messaging.modal.mcpModeSelect';
const MESSAGING_MODAL_ACTION_MCP_GROUP_TOGGLE = 'settings.messaging.modal.mcpGroupToggle';
const MESSAGING_MODAL_ACTION_MCP_SEARCH = 'settings.messaging.modal.mcpSearch';

type MessagingActionId = typeof MESSAGING_ACTION_ADD_ACCOUNT | typeof MESSAGING_ACTION_EDIT_ACCOUNT | typeof MESSAGING_ACTION_ENABLE_ACCOUNT | typeof MESSAGING_ACTION_DISABLE_ACCOUNT | typeof MESSAGING_ACTION_REMOVE_ACCOUNT;

type MessagingModalActionId = typeof MESSAGING_MODAL_ACTION_SAVE | typeof MESSAGING_MODAL_ACTION_WORKSPACE | typeof MESSAGING_MODAL_ACTION_PARAMETERS;

const { guard: isMessagingActionId } = createActionIdSet<MessagingActionId>(MESSAGING_ACTION_ADD_ACCOUNT, MESSAGING_ACTION_EDIT_ACCOUNT, MESSAGING_ACTION_ENABLE_ACCOUNT, MESSAGING_ACTION_DISABLE_ACCOUNT, MESSAGING_ACTION_REMOVE_ACCOUNT);
const { guard: isMessagingModalActionId } = createActionIdSet<MessagingModalActionId>(MESSAGING_MODAL_ACTION_SAVE, MESSAGING_MODAL_ACTION_WORKSPACE, MESSAGING_MODAL_ACTION_PARAMETERS);

export { MESSAGING_ACTION_ADD_ACCOUNT, MESSAGING_ACTION_DISABLE_ACCOUNT, MESSAGING_ACTION_EDIT_ACCOUNT, MESSAGING_ACTION_ENABLE_ACCOUNT, MESSAGING_ACTION_REMOVE_ACCOUNT, MESSAGING_MODAL_ACTION_MCP_GROUP_TOGGLE, MESSAGING_MODAL_ACTION_MCP_MODE_SELECT, MESSAGING_MODAL_ACTION_MCP_SEARCH, MESSAGING_MODAL_ACTION_MCP_SERVER_TOGGLE, MESSAGING_MODAL_ACTION_MCP_TOOL_TOGGLE, MESSAGING_MODAL_ACTION_PARAMETERS, MESSAGING_MODAL_ACTION_SAVE, MESSAGING_MODAL_ACTION_WORKSPACE, SETTINGS_MESSAGING_ACCOUNT_MODAL_ID, SETTINGS_MESSAGING_PARAMETERS_MODAL_ID, isMessagingActionId, isMessagingModalActionId };
export type { MessagingActionId, MessagingModalActionId };
