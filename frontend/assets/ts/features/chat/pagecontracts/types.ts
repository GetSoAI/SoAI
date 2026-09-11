/* SoAI - Chat feature page contracts [frontend/assets/ts/features/chat/pagecontracts/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import type { TaskCancellationResponse } from '@core/api/contracts/systemContracts.ts';
import type { TaskResponse } from '@core/api/contracts/taskContracts.ts';
import type { OpenAiTranscriptionResponse } from '@core/api/contracts/openAiResponseContracts.ts';
import type { SuccessfulMutationResponse } from '@core/api/contracts/successfulMutationContract.ts';
import type { ConversationDraftResponse, ConversationDraftSaveRequest, ConversationInputAdmission, ConversationInputEnqueueRequest, ConversationInputListResponse } from '@core/api/contracts/chatQueueDraftContracts.ts';
import type { AgentCheckpointResponse, AgentMessageWriteResponse, AgentPlanStateResponse, AgentPlanWriteRequest, AgentShellToolStopResponse, AgentTodoStateResponse, AgentTodoWriteRequest, AgentTurnCancelRequest, AgentTurnCancelResponse } from '@core/api/contracts/chatAgentContracts.ts';
import type { FileExplorerListResponse, FileExplorerSearchResponse } from '@core/api/contracts/fileExplorerContractTypes.ts';
import type { ApiQueryParameters, ApiRequestBody, RequestOptions } from '@core/api/types/request.ts';
import type { WebuiResourceEndpoints } from '@core/api/endpoints/webuiResourceEndpoints.ts';
import type { RagBatchUploadOptions } from '@core/api/endpoints/webuiRagUploads.ts';
import type { ArchivedConversationListOptions, WebuiChatEndpoints } from '@core/api/endpoints/webuiChatEndpoints.ts';
import type { WebuiUser } from '@core/api/contracts/webuiUserContracts.ts';
import type { ChatUiParameters } from '@core/types/chatParameters.ts';
import type { HostFilesystemBrowserApi, ReadOnlyFileBrowserApi } from '@core/fileexplorerbrowser/types.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { ArchivedConversationsPageResponse, ArchivedConversationResponse, ConversationBatchDeleteResponse, ConversationDeleteAllResponse, ConversationMessageSyncCursorResponse, ConversationMessageWindowResponse, ConversationMessageWriteResponse, ConversationRunningActivityResponse, WebuiConversationResponse } from '@core/api/contracts/webuiConversationContracts.ts';
import type { AskUserInteractionResolutionRequest, ComparisonTurnPreflightRequest, ComparisonTurnPreflightResponse, ConversationAttentionRenderedRequest, ConversationInteractionResolutionResponse, ConversationJsonExportRequest, ConversationMcpConfigResponse, ConversationMcpConfigUpdateRequest, ConversationMcpToolCatalogResponse, ConversationPendingInteractionResponse, ConversationPdfExportAcceptedResponse, ConversationPdfExportStartRequest, ConversationSearchConfigResponse, ConversationSearchConfigUpdateRequest, ConversationStreamStatusResponse, ConversationWorkspacePathConfigResponse, ConversationWorkspacePathConfigUpdateRequest, SecretPromptInteractionResolutionRequest, SoaiLinkResolveRequest, SoaiLinkResolveResponse, SoaiPathOpenResponse, SoaiPathOperationRequest, SoaiPathPreviewResponse, SoaiPathReadResponse, SoaiPathTokenResponse, ToolApprovalInteractionResolutionRequest } from '@core/api/contracts/webuiChatOperationContracts.ts';
import type { WebuiConversationMessageResponse } from '@core/api/contracts/webuiMessageContracts.ts';
import type { ConversationCloneRequest, ConversationCreateRequest } from '@core/api/contracts/webuiConversationRequestContracts.ts';
import type { MessageResubmitRequest, MessageTargetMutationRequest } from '@core/api/contracts/webuiMessageMutationContracts.ts';
import type { KnowledgeAttachmentClaimRequest, KnowledgeAttachmentClaimResponse, KnowledgeAttachmentCollectionResponse, KnowledgeAttachmentItemsResponse, KnowledgeAttachmentPreviewRequest, KnowledgeAttachmentPreviewResponse, KnowledgeAttachmentSummary, KnowledgeAttachmentUseRequest, KnowledgeAttachmentUseResponse, PhysicalAttachmentResponse } from '@core/api/contracts/webuiAttachmentContracts.ts';
import type { RagBatchUploadResponse, RagConfigResponse, RagConfigUpdateRequest, RagDeleteResponse, RagDocumentsResponse, RagIngestResponse, RagReindexResponse, RagUploadResponse } from '@core/api/contracts/webuiRagContracts.ts';

interface ChatPreferencesManager {
    model?: string;
    parameters?: JsonObject;
    [key: string]: JsonValue | undefined;
}

type ModelStreamReadiness = {
    status: 'ready' | 'timed_out' | 'failed';
    hasPayload: boolean;
    reason: string | null;
};

interface ChatSystemApi {
    cancelTask: (taskId: string, reason?: string | null) => Promise<TaskCancellationResponse>;
}

interface ChatTasksApi {
    get: (taskId: string, options?: RequestOptions) => Promise<TaskResponse>;
}

interface ChatModelsApi {
    updateParameters: (modelId: string, parameters: JsonValue) => Promise<SuccessfulMutationResponse>;
}

interface ChatPreferencesApi {
    get: () => Promise<JsonObject>;
    update: (preferences: JsonObject) => Promise<JsonObject>;
}

interface ChatAuthApi {
    getMe: () => Promise<WebuiUser>;
}

interface ChatUsersApi {
    workspaceBrowser: HostFilesystemBrowserApi;
}

interface ChatConversationMessagesApi {
    window: (conversationId: string, options: ApiQueryParameters, requestOptions?: RequestOptions) => Promise<ConversationMessageWindowResponse>;
    runningActivity: (conversationId: string, requestOptions?: RequestOptions) => Promise<ConversationRunningActivityResponse>;
    replace: (conversationId: string, messages: JsonValue, expectedLastModifiedAtMs: number) => Promise<ConversationMessageWriteResponse>;
    append: (conversationId: string, messages: JsonValue, expectedLastModifiedAtMs: number) => Promise<ConversationMessageWriteResponse>;
    resubmit: (conversationId: string, payload: MessageResubmitRequest) => Promise<ConversationMessageWriteResponse>;
    truncate: (conversationId: string, payload: MessageTargetMutationRequest) => Promise<ConversationMessageWriteResponse>;
    deleteMessage: (conversationId: string, payload: MessageTargetMutationRequest) => Promise<ConversationMessageWriteResponse>;
    syncCursor: (conversationId: string) => Promise<ConversationMessageSyncCursorResponse>;
}

interface ChatAttachmentsApi {
    stage: (
        conversationId: string,
        payload: {
            file: File;
            displayName: string;
            source: string;
            clientAttachmentId: string;
            clientRequestId: string;
        },
        options?: RequestOptions
    ) => Promise<PhysicalAttachmentResponse>;
    get: (conversationId: string, attachmentId: string, options?: RequestOptions) => Promise<PhysicalAttachmentResponse>;
    delete: (conversationId: string, attachmentId: string, options?: RequestOptions) => Promise<void>;
    contentPath: (conversationId: string, attachmentId: string, download: boolean) => string;
    knowledge: ChatKnowledgeAttachmentsApi;
}

interface ChatKnowledgeAttachmentsApi {
    reusable: (options?: { query?: string | undefined; limit?: number | undefined; signal?: AbortSignal | undefined } | null) => Promise<KnowledgeAttachmentCollectionResponse>;
    draft: (conversationId: string, options?: { previewLimit?: number; signal?: AbortSignal | undefined } | null) => Promise<KnowledgeAttachmentCollectionResponse>;
    claim: (conversationId: string, payload: KnowledgeAttachmentClaimRequest, options?: RequestOptions) => Promise<KnowledgeAttachmentClaimResponse>;
    get: (conversationId: string, knowledgeAttachmentId: string, options?: RequestOptions) => Promise<KnowledgeAttachmentSummary>;
    delete: (conversationId: string, knowledgeAttachmentId: string, options?: RequestOptions) => Promise<KnowledgeAttachmentSummary>;
    cancel: (conversationId: string, knowledgeAttachmentId: string, options?: RequestOptions) => Promise<KnowledgeAttachmentSummary>;
    items: (conversationId: string, knowledgeAttachmentId: string, options?: { limit?: number | undefined; cursorItemIndex?: number | undefined; cursorId?: number | undefined; status?: string | undefined; query?: string | undefined; signal?: AbortSignal | undefined } | null) => Promise<KnowledgeAttachmentItemsResponse>;
    previewItem: (conversationId: string, knowledgeAttachmentId: string, itemId: string, payload: KnowledgeAttachmentPreviewRequest, options?: RequestOptions) => Promise<KnowledgeAttachmentPreviewResponse>;
    useItems: (conversationId: string, payload: KnowledgeAttachmentUseRequest, options?: RequestOptions) => Promise<KnowledgeAttachmentUseResponse>;
}

interface ChatConversationRagApi {
    getConfig: (conversationId: string, options?: RequestOptions) => Promise<RagConfigResponse>;
    updateConfig: (conversationId: string, payload: RagConfigUpdateRequest) => Promise<RagConfigResponse>;
    listDocuments: (conversationId: string, options?: ({ limit?: number; offset?: number; includeDocuments?: boolean } & RequestOptions) | null) => Promise<RagDocumentsResponse>;
    uploadDocument: (conversationId: string, file: File) => Promise<RagUploadResponse>;
    uploadDocumentsBatch: (conversationId: string, files: readonly File[], options?: RagBatchUploadOptions) => Promise<RagBatchUploadResponse>;
    ingestFileExplorer: (conversationId: string, payload: { path: string; recursive?: boolean }, options?: RequestOptions) => Promise<RagIngestResponse>;
    deleteDocument: (conversationId: string, documentId: string, options?: RequestOptions) => Promise<RagDeleteResponse>;
    reindex: (conversationId: string, embeddingModel: string, options?: RequestOptions) => Promise<RagReindexResponse>;
}

interface ChatConversationSearchApi {
    getConfig: (conversationId: string, options?: RequestOptions) => Promise<ConversationSearchConfigResponse>;
    updateConfig: (conversationId: string, payload: ConversationSearchConfigUpdateRequest) => Promise<ConversationSearchConfigResponse>;
}

interface ChatConversationMcpApi {
    getTools: (conversationId: string, options?: RequestOptions) => Promise<ConversationMcpToolCatalogResponse>;
    getConfig: (conversationId: string, options?: RequestOptions) => Promise<ConversationMcpConfigResponse>;
    updateConfig: (conversationId: string, payload: ConversationMcpConfigUpdateRequest) => Promise<ConversationMcpConfigResponse>;
}

interface ChatConversationAgentApi {
    cancelTurn: (conversationId: string, turnId: string, request: AgentTurnCancelRequest) => Promise<AgentTurnCancelResponse>;
    startCompaction: (conversationId: string, payload: { model: string }) => Promise<AgentCheckpointResponse>;
    regenerateCompaction: (conversationId: string, payload: { assistantTurnAtMs: number }) => Promise<AgentCheckpointResponse>;
    removeCompactionBoundary: (conversationId: string, payload: { assistantTurnAtMs: number; modelVariantIndex: number; toolCallId: string; expectedLastModifiedAtMs: number }) => Promise<AgentMessageWriteResponse>;
    stopShellToolCall: (conversationId: string, payload: { assistantTurnAtMs: number; modelVariantIndex: number; toolCallId: string }) => Promise<AgentShellToolStopResponse>;
    todoWrite: (conversationId: string, payload: AgentTodoWriteRequest) => Promise<AgentTodoStateResponse>;
    planWrite: (conversationId: string, payload: AgentPlanWriteRequest) => Promise<AgentPlanStateResponse>;
}

interface ChatConversationWorkspacePathApi {
    getConfig: (conversationId: string, options?: RequestOptions) => Promise<ConversationWorkspacePathConfigResponse>;
    updateConfig: (conversationId: string, payload: ConversationWorkspacePathConfigUpdateRequest) => Promise<ConversationWorkspacePathConfigResponse>;
}

interface ChatConversationInputQueueApi {
    list: (conversationId: string) => Promise<ConversationInputListResponse>;
    enqueue: (conversationId: string, payload: ConversationInputEnqueueRequest) => Promise<ConversationInputAdmission>;
    cancel: (conversationId: string, inputId: string) => Promise<void>;
}

interface ChatConversationDraftApi {
    get: (conversationId: string, options?: RequestOptions) => Promise<ConversationDraftResponse>;
    save: (conversationId: string, payload: ConversationDraftSaveRequest, options?: RequestOptions) => Promise<ConversationDraftResponse>;
    delete: (conversationId: string, options?: RequestOptions) => Promise<ConversationDraftResponse>;
}

interface ChatConversationInteractionApi<TResolutionRequest> {
    pending: (conversationId: string) => Promise<ConversationPendingInteractionResponse>;
    resolve: (conversationId: string, taskId: string, request: TResolutionRequest) => Promise<ConversationInteractionResolutionResponse>;
}

interface ChatConversationInteractionsApi {
    askUser: ChatConversationInteractionApi<AskUserInteractionResolutionRequest>;
    vaultSecretRequest: ChatConversationInteractionApi<SecretPromptInteractionResolutionRequest>;
    toolApproval: ChatConversationInteractionApi<ToolApprovalInteractionResolutionRequest>;
    attentionRendered: (conversationId: string, request: ConversationAttentionRenderedRequest) => Promise<void>;
}

interface ChatConversationAssistantMessagesApi {
    streamState: (conversationId: string, assistantTurnTimestamp: number, modelVariantIndex: number) => Promise<WebuiConversationMessageResponse>;
}

interface ChatComparisonTurnsApi {
    preflight: (conversationId: string, request: ComparisonTurnPreflightRequest) => Promise<ComparisonTurnPreflightResponse>;
}

interface ChatSoaiLinksApi {
    resolve: (conversationId: string, payload: SoaiLinkResolveRequest, options?: RequestOptions) => Promise<SoaiLinkResolveResponse>;
}

interface ChatSoaiPathsApi {
    browse: (conversationId: string, payload: { query: string | null; limit: number }, options?: RequestOptions) => Promise<FileExplorerListResponse | FileExplorerSearchResponse>;
    preview: (conversationId: string, payload: SoaiPathOperationRequest, options?: RequestOptions) => Promise<SoaiPathPreviewResponse>;
    read: (conversationId: string, payload: SoaiPathOperationRequest, options?: RequestOptions) => Promise<SoaiPathReadResponse>;
    download: (conversationId: string, payload: SoaiPathOperationRequest, options?: RequestOptions) => Promise<Response | { state: 'unavailable' }>;
    open: (conversationId: string, payload: SoaiPathOperationRequest, options?: RequestOptions) => Promise<SoaiPathOpenResponse>;
    token: (conversationId: string, payload: SoaiPathOperationRequest, options?: RequestOptions) => Promise<SoaiPathTokenResponse>;
}

interface ChatConversationPdfExportApi {
    start: (file: Blob, request: ConversationPdfExportStartRequest, options?: RequestOptions) => Promise<ConversationPdfExportAcceptedResponse>;
    download: (taskId: string, options?: RequestOptions) => Promise<Response>;
}

interface ChatConversationJsonExportApi {
    download: (conversationId: string, payload: ConversationJsonExportRequest, options?: RequestOptions) => Promise<Response>;
}

interface ChatWebuiChatApi {
    list: () => Promise<WebuiConversationResponse[]>;
    create: (payload: ConversationCreateRequest, options?: RequestOptions) => Promise<WebuiConversationResponse>;
    clone: (conversationId: string, payload: ConversationCloneRequest) => Promise<WebuiConversationResponse>;
    get: (conversationId: string) => Promise<WebuiConversationResponse>;
    delete: (conversationId: string) => Promise<void>;
    batchDelete: (conversationIds: readonly string[]) => Promise<ConversationBatchDeleteResponse>;
    deleteAll: () => Promise<ConversationDeleteAllResponse>;
    messages: ChatConversationMessagesApi;
    attachments: ChatAttachmentsApi;
    updateTitle: (conversationId: string, title: string) => Promise<WebuiConversationResponse>;
    updateSettings: (conversationId: string, payload: JsonObject) => Promise<WebuiConversationResponse>;
    updateColor: (conversationId: string, color: string | null) => Promise<WebuiConversationResponse>;
    updateFavorite: (conversationId: string, isFavorite: boolean) => Promise<WebuiConversationResponse>;
    updateArchived: (conversationId: string, isArchived: boolean) => Promise<WebuiConversationResponse>;
    listArchived: (options?: ArchivedConversationListOptions | null, requestOptions?: RequestOptions) => Promise<ArchivedConversationsPageResponse>;
    searchArchived: (options?: ApiQueryParameters | null, requestOptions?: RequestOptions) => Promise<ArchivedConversationResponse[]>;
    workspacePath: ChatConversationWorkspacePathApi;
    rag: ChatConversationRagApi;
    search: ChatConversationSearchApi;
    mcp: ChatConversationMcpApi;
    agent: ChatConversationAgentApi;
    inputQueue: ChatConversationInputQueueApi;
    presets: WebuiChatEndpoints['chat']['presets'];
    draft: ChatConversationDraftApi;
    interactions: ChatConversationInteractionsApi;
    assistantMessages: ChatConversationAssistantMessagesApi;
    streamStatus: { get: (conversationId: string, options?: RequestOptions) => Promise<ConversationStreamStatusResponse> };
    comparisonTurns: ChatComparisonTurnsApi;
    soaiLinks: ChatSoaiLinksApi;
    soaiPaths: ChatSoaiPathsApi;
    exportPdf: ChatConversationPdfExportApi;
    exportJson: ChatConversationJsonExportApi;
}

interface ChatPageApi {
    fileExplorer: ReadOnlyFileBrowserApi;
    fetchAsset: (path: string, options?: { timeout?: number; responseType?: 'text' | 'json' | 'blob'; signal?: AbortSignal }) => Promise<ApiResponsePayload>;
    request: (method: string, endpoint: string, body?: ApiRequestBody, options?: RequestOptions) => Promise<ApiResponsePayload>;
    system: ChatSystemApi;
    tasks: ChatTasksApi;
    models: ChatModelsApi;
    webui: {
        auth: ChatAuthApi;
        preferences: ChatPreferencesApi;
        prompts: WebuiResourceEndpoints['prompts'];
        users: ChatUsersApi;
        chat: ChatWebuiChatApi;
        media: {
            audio: {
                transcriptions: {
                    create: (payload: FormData, options?: RequestOptions) => Promise<OpenAiTranscriptionResponse>;
                };
                speech: {
                    create: (payload: JsonObject, options?: RequestOptions) => Promise<Response>;
                };
            };
        };
    };
}

export type { ChatConversationMcpApi, ChatConversationRagApi, ChatConversationSearchApi, ChatKnowledgeAttachmentsApi, ChatPageApi, ChatPreferencesManager, ChatSoaiPathsApi, ChatUiParameters, ModelStreamReadiness };
