/* SoAI - Chat feature conversation settings parsing [frontend/assets/ts/features/chat/conversationsettings/conversationSettingsParsing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationMcpConfigResponse, ConversationMcpToolCatalogResponse, ConversationMcpToolEntry, ConversationSearchConfigResponse, ConversationWorkspacePathConfigResponse } from '@core/api/contracts/webuiChatOperationContracts.ts';
import type { RagConfigResponse, RagDocumentResponse, RagDocumentsResponse } from '@core/api/contracts/webuiRagContracts.ts';
import { AUTO_EMBEDDING_MODEL_SELECTOR } from '@core/chat/protocols.ts';
import { normalizeMcpServerId } from '@core/mcp/serverSettings.ts';
import type { ConversationWorkspacePathConfig, McpCanonicalToolDefaults, McpConfig, McpTool, RagConfig, RagDocument, RagDocumentsPage, SearchConfig } from '@features/chat/conversationsettings/settingsModels.ts';

const normalizeEmbeddingModel = (value: string | null): string | null => {
    if (value === null) {
        return null;
    }
    const trimmed = value.trim();
    if (!trimmed || trimmed === AUTO_EMBEDDING_MODEL_SELECTOR) {
        return null;
    }
    return trimmed;
};

const parseRagConfig = (response: RagConfigResponse): RagConfig => ({
    enabled: response.enabled,
    retrievalStrategy: response.retrievalStrategy,
    topK: response.topK,
    similarityThreshold: response.similarityThreshold,
    chunkingStrategy: response.chunkingStrategy,
    chunkSize: response.chunkSize,
    chunkOverlap: response.chunkOverlap,
    embeddingModel: normalizeEmbeddingModel(response.embeddingModel)
});

const parseRagDocument = (response: RagDocumentResponse): RagDocument => ({
    id: response.id,
    filename: response.filename,
    fileSizeBytes: response.fileSizeBytes,
    status: response.status.toLowerCase(),
    statusDetails: response.statusDetails,
    totalChunks: response.totalChunks,
    processedChunks: response.processedChunks,
    createdAtMs: response.createdAtMs,
    errorMessage: response.errorMessage
});

const parseRagDocumentsPage = (response: RagDocumentsResponse): RagDocumentsPage => ({
    documents: response.documents.map(parseRagDocument),
    count: response.count,
    chunkCount: response.chunkCount,
    statusCounts: { ...response.statusCounts },
    limit: response.limit,
    offset: response.offset
});

const parseMcpConfig = (response: ConversationMcpConfigResponse): McpConfig => ({
    defaultTools: [...response.defaultTools],
    planTools: [...response.planTools],
    executeTools: [...response.executeTools],
    serverConfigs: { ...response.serverConfigs },
    toolsEnabled: response.toolsEnabled,
    toolApprovalRequired: response.toolApprovalRequired,
    knowledgeState: { ...response.knowledgeState }
});

const parseMcpTool = (response: ConversationMcpToolEntry): McpTool => {
    const serverId = response.serverId === null ? 'builtin' : normalizeMcpServerId(response.serverId);
    return {
        name: response.name,
        definition: response.definition,
        source: response.source,
        serverId,
        serverName: response.serverName,
        allowed: response.allowed,
        blockedReason: response.blockedReason,
        isBuiltin: response.source === 'builtin' || serverId === 'builtin',
        knowledgeRole: response.knowledgeRole,
        icons: response.icons === null ? [] : [...response.icons]
    };
};

const parseMcpTools = (response: ConversationMcpToolCatalogResponse): McpTool[] => response.tools.map(parseMcpTool);

const parseMcpCanonicalToolDefaults = (response: ConversationMcpToolCatalogResponse): McpCanonicalToolDefaults => ({
    defaultTools: [...response.canonicalDefaultTools],
    planTools: [...response.canonicalPlanTools],
    executeTools: [...response.canonicalExecuteTools]
});

const parseSearchConfig = (response: ConversationSearchConfigResponse): SearchConfig => ({
    enabled: response.enabled,
    defaultProvider: response.defaultProvider,
    maxResults: response.maxResults,
    availableProviders: [...response.availableProviders]
});

const parseConversationWorkspacePathConfig = (response: ConversationWorkspacePathConfigResponse): ConversationWorkspacePathConfig => ({
    workspacePath: response.workspacePath,
    effectiveWorkspacePath: response.effectiveWorkspacePath,
    effectiveRootFingerprint: response.effectiveRootFingerprint,
    isValid: response.isValid,
    validationCode: response.validationCode,
    validationMessage: response.validationMessage
});

export { parseConversationWorkspacePathConfig, parseMcpCanonicalToolDefaults, parseMcpConfig, parseMcpTools, parseRagConfig, parseRagDocumentsPage, parseSearchConfig };
