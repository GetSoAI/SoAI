/* SoAI - Frontend WebUI chat configuration serialization [frontend/assets/ts/core/api/contracts/webuiChatConfigurationSerialization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationMcpConfigUpdateRequest, ConversationSearchConfigUpdateRequest, ConversationWorkspacePathConfigUpdateRequest } from '@core/api/contracts/webuiChatOperationContractTypes.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

const serializeWorkspacePathConfigUpdate = (request: ConversationWorkspacePathConfigUpdateRequest): JsonObject => ({
    'workspace_path': request.workspacePath
});

const serializeSearchConfigUpdate = (request: ConversationSearchConfigUpdateRequest): JsonObject => {
    const serialized: JsonObject = {};
    if (request.enabled !== undefined) serialized['enabled'] = request.enabled;
    if (request.defaultProvider !== undefined) serialized['default_provider'] = request.defaultProvider;
    if (request.maxResults !== undefined) serialized['max_results'] = request.maxResults;
    return serialized;
};

const serializeMcpConfigUpdate = (request: ConversationMcpConfigUpdateRequest): JsonObject => {
    const serialized: JsonObject = {};
    if (request.defaultTools !== undefined) serialized['default_tools'] = request.defaultTools;
    if (request.planTools !== undefined) serialized['plan_tools'] = request.planTools;
    if (request.executeTools !== undefined) serialized['execute_tools'] = request.executeTools;
    if (request.serverConfigs !== undefined) serialized['server_configs'] = request.serverConfigs;
    if (request.toolsEnabled !== undefined) serialized['tools_enabled'] = request.toolsEnabled;
    if (request.toolApprovalRequired !== undefined) serialized['tool_approval_required'] = request.toolApprovalRequired;
    return serialized;
};

export { serializeMcpConfigUpdate, serializeSearchConfigUpdate, serializeWorkspacePathConfigUpdate };
