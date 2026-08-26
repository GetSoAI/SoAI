/* SoAI - Chat feature strings knowledge MCP agent [frontend/assets/ts/features/chat/chattemplates/chatStringsKnowledgeMcpAgent.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SanitizerApi } from '@core/pagecontext/public.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ChatTemplateStringSet } from '@features/chat/chattemplates/stringSetTypes.ts';

type KnowledgeMcpAgent = Pick<
    ChatTemplateStringSet,
    | 'ragTitle'
    | 'ragEnabled'
    | 'ragEnabledHint'
    | 'ragRetrievalStrategy'
    | 'ragRetrievalSimilarity'
    | 'ragRetrievalMmr'
    | 'ragRetrievalHybrid'
    | 'ragTopK'
    | 'ragSimilarityThreshold'
    | 'ragChunkingStrategy'
    | 'ragChunkingTokenBased'
    | 'ragChunkingFixedSize'
    | 'ragChunkingParagraph'
    | 'ragChunkingSemantic'
    | 'ragChunkSize'
    | 'ragChunkOverlap'
    | 'ragEmbeddingModel'
    | 'ragEmbeddingHint'
    | 'knowledgeTitle'
    | 'memoryTitle'
    | 'memoryUserMemoriesTitle'
    | 'memoryDescription'
    | 'memoryOpenProfile'
    | 'memoryRefresh'
    | 'memoryEmpty'
    | 'knowledgeDownloadModel'
    | 'knowledgeDownloadModelAttr'
    | 'webSearchTitle'
    | 'webSearchEnabled'
    | 'webSearchProvider'
    | 'webSearchProviderPlaceholder'
    | 'webSearchMaxResults'
    | 'mcpTitle'
    | 'mcpServers'
    | 'mcpServersEmpty'
    | 'mcpTools'
    | 'mcpToolsEmpty'
    | 'mcpAutomation'
    | 'mcpToolsEnabled'
    | 'mcpToolsEnabledHint'
    | 'mcpToolApprovalRequired'
    | 'mcpToolApprovalRequiredHint'
    | 'mcpDefaultToolsTitle'
    | 'mcpDefaultToolsOpen'
    | 'mcpDefaultToolsOpenAttr'
    | 'mcpDefaultToolsSummary'
    | 'mcpDefaultToolsSummaryHint'
    | 'mcpDefaultToolsModalTitle'
    | 'mcpResetToolsDescription'
    | 'mcpResetToolsLabel'
    | 'mcpResetToolsTitle'
    | 'modelSettingsTitle'
    | 'modelContextWindowTokensLabel'
    | 'modelContextWindowTokensHint'
    | 'agentModeChat'
    | 'agentModeCycleTooltip'
    | 'agentCompact'
    | 'toolbarExpand'
    | 'toolbarSelect'
    | 'toolbarArchive'
    | 'toolbarBatchArchive'
    | 'toolbarBatchDelete'
    | 'toolbarBatchClone'
    | 'toolbarExitSelect'
>;

const resolveKnowledgeMcpAgentTemplateStrings = (sanitizer: SanitizerApi): KnowledgeMcpAgent => {
    return {
        ragTitle: i18n.html(sanitizer, 'chat.configuration.rag.title'),
        ragEnabled: i18n.html(sanitizer, 'chat.configuration.rag.enabled'),
        ragEnabledHint: i18n.html(sanitizer, 'chat.configuration.rag.enabledHint'),
        ragRetrievalStrategy: i18n.html(sanitizer, 'chat.configuration.rag.retrievalStrategy'),
        ragRetrievalSimilarity: i18n.html(sanitizer, 'chat.configuration.rag.retrievalSimilarity'),
        ragRetrievalMmr: i18n.html(sanitizer, 'chat.configuration.rag.retrievalMmr'),
        ragRetrievalHybrid: i18n.html(sanitizer, 'chat.configuration.rag.retrievalHybrid'),
        ragTopK: i18n.html(sanitizer, 'chat.configuration.rag.topK'),
        ragSimilarityThreshold: i18n.html(sanitizer, 'chat.configuration.rag.similarityThreshold'),
        ragChunkingStrategy: i18n.html(sanitizer, 'chat.configuration.rag.chunkingStrategy'),
        ragChunkingTokenBased: i18n.html(sanitizer, 'chat.configuration.rag.chunkingTokenBased'),
        ragChunkingFixedSize: i18n.html(sanitizer, 'chat.configuration.rag.chunkingFixedSize'),
        ragChunkingParagraph: i18n.html(sanitizer, 'chat.configuration.rag.chunkingParagraph'),
        ragChunkingSemantic: i18n.html(sanitizer, 'chat.configuration.rag.chunkingSemantic'),
        ragChunkSize: i18n.html(sanitizer, 'chat.configuration.rag.chunkSize'),
        ragChunkOverlap: i18n.html(sanitizer, 'chat.configuration.rag.chunkOverlap'),
        ragEmbeddingModel: i18n.html(sanitizer, 'chat.configuration.rag.embeddingModel'),
        ragEmbeddingHint: i18n.html(sanitizer, 'chat.configuration.rag.embeddingHint'),
        knowledgeTitle: i18n.html(sanitizer, 'chat.configuration.knowledge.title'),
        memoryTitle: i18n.html(sanitizer, 'chat.configuration.memory.title'),
        memoryUserMemoriesTitle: i18n.html(sanitizer, 'chat.configuration.memory.userMemoriesTitle'),
        memoryDescription: i18n.html(sanitizer, 'chat.configuration.memory.description'),
        memoryOpenProfile: i18n.html(sanitizer, 'chat.configuration.memory.openProfile'),
        memoryRefresh: i18n.html(sanitizer, 'chat.configuration.memory.refresh'),
        memoryEmpty: i18n.html(sanitizer, 'chat.configuration.memory.empty'),
        knowledgeDownloadModel: i18n.html(sanitizer, 'chat.configuration.knowledge.downloadModel'),
        knowledgeDownloadModelAttr: i18n.attr(sanitizer, 'chat.configuration.knowledge.downloadModel'),
        webSearchTitle: i18n.html(sanitizer, 'chat.configuration.webSearch.title'),
        webSearchEnabled: i18n.html(sanitizer, 'chat.configuration.webSearch.enabled'),
        webSearchProvider: i18n.html(sanitizer, 'chat.configuration.webSearch.provider'),
        webSearchProviderPlaceholder: i18n.html(sanitizer, 'chat.configuration.webSearch.providerPlaceholder'),
        webSearchMaxResults: i18n.html(sanitizer, 'chat.configuration.webSearch.maxResults'),
        mcpTitle: i18n.html(sanitizer, 'chat.configuration.mcp.title'),
        mcpServers: i18n.html(sanitizer, 'chat.configuration.mcp.servers'),
        mcpServersEmpty: i18n.html(sanitizer, 'chat.configuration.mcp.noServers'),
        mcpTools: i18n.html(sanitizer, 'chat.configuration.mcp.tools'),
        mcpToolsEmpty: i18n.html(sanitizer, 'chat.configuration.mcp.noTools'),
        mcpAutomation: i18n.html(sanitizer, 'chat.configuration.mcp.automation'),
        mcpToolsEnabled: i18n.html(sanitizer, 'chat.configuration.mcp.tools_enabled'),
        mcpToolsEnabledHint: i18n.html(sanitizer, 'chat.configuration.mcp.toolsEnabledHint'),
        mcpToolApprovalRequired: i18n.html(sanitizer, 'chat.configuration.mcp.tool_approval_required'),
        mcpToolApprovalRequiredHint: i18n.html(sanitizer, 'chat.configuration.mcp.toolApprovalRequiredHint'),
        mcpDefaultToolsTitle: i18n.html(sanitizer, 'chat.configuration.mcp.defaultTools.title'),
        mcpDefaultToolsOpen: i18n.html(sanitizer, 'chat.configuration.mcp.defaultTools.open'),
        mcpDefaultToolsOpenAttr: i18n.attr(sanitizer, 'chat.configuration.mcp.defaultTools.open'),
        mcpDefaultToolsSummary: i18n.html(sanitizer, 'chat.configuration.mcp.defaultTools.summary', { count: 0 }),
        mcpDefaultToolsSummaryHint: i18n.html(sanitizer, 'chat.configuration.mcp.defaultTools.summaryHint'),
        mcpDefaultToolsModalTitle: i18n.html(sanitizer, 'chat.configuration.mcp.defaultTools.modalTitle'),
        mcpResetToolsDescription: i18n.html(sanitizer, 'chat.configuration.mcp.resetToolsDescription', { mode: '{mode}' }),
        mcpResetToolsLabel: i18n.html(sanitizer, 'chat.configuration.mcp.resetToolsLabel'),
        mcpResetToolsTitle: i18n.html(sanitizer, 'chat.configuration.mcp.resetToolsTitle'),
        modelSettingsTitle: i18n.html(sanitizer, 'chat.configuration.model_settings.title'),
        modelContextWindowTokensLabel: i18n.html(sanitizer, 'chat.configuration.model_settings.contextWindowTokensLabel'),
        modelContextWindowTokensHint: i18n.html(sanitizer, 'chat.configuration.model_settings.contextWindowTokensHint'),
        agentModeChat: i18n.html(sanitizer, 'chat.agent.mode.chat'),
        agentModeCycleTooltip: i18n.attr(sanitizer, 'chat.agent.mode.cycleTooltip'),
        agentCompact: i18n.html(sanitizer, 'chat.agent.compact.label'),
        toolbarExpand: i18n.attr(sanitizer, 'chat.toolbar.expand'),
        toolbarSelect: i18n.attr(sanitizer, 'chat.toolbar.select'),
        toolbarArchive: i18n.attr(sanitizer, 'chat.toolbar.archive'),
        toolbarBatchArchive: i18n.attr(sanitizer, 'chat.toolbar.batchArchive'),
        toolbarBatchDelete: i18n.attr(sanitizer, 'chat.toolbar.batchDelete'),
        toolbarBatchClone: i18n.attr(sanitizer, 'chat.toolbar.batchClone'),
        toolbarExitSelect: i18n.attr(sanitizer, 'chat.toolbar.exitSelect')
    };
};

export { resolveKnowledgeMcpAgentTemplateStrings };
