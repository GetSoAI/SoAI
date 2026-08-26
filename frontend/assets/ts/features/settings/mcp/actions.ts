/* SoAI - Settings feature MCP actions [frontend/assets/ts/features/settings/mcp/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';

export const MCP_ACTION_REFRESH = 'settings.mcp.refresh';
export const MCP_ACTION_SECTION_TOGGLE = 'settings.mcp.section.toggle';

export const MCP_ACTION_SERVER_ADD = 'settings.mcp.server.add';
export const MCP_ACTION_SERVER_EDIT = 'settings.mcp.server.edit';
export const MCP_ACTION_SERVER_DELETE = 'settings.mcp.server.delete';
export const MCP_ACTION_SERVER_CONNECT = 'settings.mcp.server.connect';
export const MCP_ACTION_SERVER_DISCONNECT = 'settings.mcp.server.disconnect';
export const MCP_ACTION_SERVER_AUTHORIZE = 'settings.mcp.server.authorize';
export const MCP_ACTION_SERVER_CLEAR_AUTH = 'settings.mcp.server.clearAuth';

export const MCP_ACTION_SEARCH_EDIT = 'settings.mcp.search.edit';
export const MCP_ACTION_SEARCH_DELETE = 'settings.mcp.search.delete';

export const MCP_ACTION_ROOT_CANCEL = 'settings.mcp.root.cancel';
export const MCP_ACTION_ROOT_EDIT = 'settings.mcp.root.edit';
export const MCP_ACTION_ROOT_DELETE = 'settings.mcp.root.delete';

export const MCP_ACTION_INTERACTION_RESOLVE = 'settings.mcp.interaction.resolve';

export const MCP_ACTION_ACCESS_TOKEN_CREATE = 'settings.mcp.accessToken.create';
export const MCP_ACTION_ACCESS_TOKEN_REVOKE = 'settings.mcp.accessToken.revoke';

export const MCP_ACTION_SERVER_ENABLED_CHANGE = 'settings.mcp.server.enabled.change';
export const MCP_ACTION_SEARCH_PROVIDER_CHANGE = 'settings.mcp.search.provider.change';
export const MCP_ACTION_INTERACTION_ACTION_CHANGE = 'settings.mcp.interaction.action.change';

export type McpClickActionId = typeof MCP_ACTION_REFRESH | typeof MCP_ACTION_SECTION_TOGGLE | typeof MCP_ACTION_SERVER_ADD | typeof MCP_ACTION_SERVER_EDIT | typeof MCP_ACTION_SERVER_DELETE | typeof MCP_ACTION_SERVER_CONNECT | typeof MCP_ACTION_SERVER_DISCONNECT | typeof MCP_ACTION_SERVER_AUTHORIZE | typeof MCP_ACTION_SERVER_CLEAR_AUTH | typeof MCP_ACTION_SEARCH_EDIT | typeof MCP_ACTION_SEARCH_DELETE | typeof MCP_ACTION_ROOT_CANCEL | typeof MCP_ACTION_ROOT_EDIT | typeof MCP_ACTION_ROOT_DELETE | typeof MCP_ACTION_INTERACTION_RESOLVE | typeof MCP_ACTION_ACCESS_TOKEN_CREATE | typeof MCP_ACTION_ACCESS_TOKEN_REVOKE;

export type McpChangeActionId = typeof MCP_ACTION_SERVER_ENABLED_CHANGE | typeof MCP_ACTION_SEARCH_PROVIDER_CHANGE | typeof MCP_ACTION_INTERACTION_ACTION_CHANGE;

const { guard: isMcpClickActionId } = createActionIdSet(MCP_ACTION_REFRESH, MCP_ACTION_SECTION_TOGGLE, MCP_ACTION_SERVER_ADD, MCP_ACTION_SERVER_EDIT, MCP_ACTION_SERVER_DELETE, MCP_ACTION_SERVER_CONNECT, MCP_ACTION_SERVER_DISCONNECT, MCP_ACTION_SERVER_AUTHORIZE, MCP_ACTION_SERVER_CLEAR_AUTH, MCP_ACTION_SEARCH_EDIT, MCP_ACTION_SEARCH_DELETE, MCP_ACTION_ROOT_CANCEL, MCP_ACTION_ROOT_EDIT, MCP_ACTION_ROOT_DELETE, MCP_ACTION_INTERACTION_RESOLVE, MCP_ACTION_ACCESS_TOKEN_CREATE, MCP_ACTION_ACCESS_TOKEN_REVOKE);

const { guard: isMcpChangeActionId } = createActionIdSet(MCP_ACTION_SERVER_ENABLED_CHANGE, MCP_ACTION_SEARCH_PROVIDER_CHANGE, MCP_ACTION_INTERACTION_ACTION_CHANGE);

export { isMcpChangeActionId, isMcpClickActionId };
