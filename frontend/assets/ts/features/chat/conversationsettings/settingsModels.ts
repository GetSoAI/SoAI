/* SoAI - Chat feature settings models [frontend/assets/ts/features/chat/conversationsettings/settingsModels.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { McpCanonicalToolDefaults, McpConfigBase, McpFormValues, McpServerGroup, McpTool, McpToolMode } from '@core/mcp/configTypes.ts';

type McpKnowledgeBlockingReason = 'disabled' | 'empty' | 'model_without_tool_calling' | 'missing_required_tools';

type McpKnowledgeRole = 'required_access' | 'management';

type McpKnowledgeState = {
    ragEnabled: boolean;
    documentCount: number;
    autoManaged: boolean;
    toolsLocked: boolean;
    forceToolsEnabled: boolean;
    ready: boolean;
    blockingReason: McpKnowledgeBlockingReason | null;
};

type RagConfig = {
    enabled: boolean;
    retrievalStrategy: string;
    topK: number;
    similarityThreshold: number;
    chunkingStrategy: string;
    chunkSize: number;
    chunkOverlap: number;
    embeddingModel: string | null;
};

type RagDocument = {
    id: string;
    filename: string;
    fileSizeBytes: number | null;
    status: string;
    statusDetails: string | null;
    totalChunks: number | null;
    processedChunks: number | null;
    createdAtMs: number | null;
    errorMessage: string | null;
};

type RagDocumentStatusCounts = {
    queued: number;
    fetching: number;
    parsing: number;
    chunking: number;
    embedding: number;
    completed: number;
    error: number;
};

type RagDocumentsPage = {
    documents: RagDocument[];
    count: number;
    chunkCount: number;
    statusCounts: RagDocumentStatusCounts;
    limit: number;
    offset: number;
};

type McpConfig = McpConfigBase<McpKnowledgeState | null>;

type ServerGroup = McpServerGroup;

type SearchConfig = {
    enabled: boolean;
    defaultProvider: string | null;
    maxResults: number;
    availableProviders: string[];
};

type ConversationWorkspacePathConfig = {
    workspacePath: string | null;
    effectiveWorkspacePath: string | null;
    effectiveRootFingerprint: string | null;
    isValid: boolean;
    validationCode: string | null;
    validationMessage: string | null;
};

type SettingsState = {
    conversationId: string | null;
    ragConfig: RagConfig | null;
    searchConfig: SearchConfig | null;
    workspacePathConfig: ConversationWorkspacePathConfig | null;
    mcpConfig: McpConfig | null;
    mcpTools: McpTool[];
    mcpCanonicalToolDefaults: McpCanonicalToolDefaults | null;
};

const createDefaultState = (conversationId: string | null = null): SettingsState => ({
    conversationId,
    ragConfig: null,
    searchConfig: null,
    workspacePathConfig: null,
    mcpConfig: null,
    mcpTools: [],
    mcpCanonicalToolDefaults: null
});

export { createDefaultState };
export type { ConversationWorkspacePathConfig, McpCanonicalToolDefaults, McpConfig, McpFormValues, McpKnowledgeBlockingReason, McpKnowledgeRole, McpKnowledgeState, McpTool, McpToolMode, RagConfig, RagDocument, RagDocumentStatusCounts, RagDocumentsPage, SearchConfig, ServerGroup, SettingsState };
