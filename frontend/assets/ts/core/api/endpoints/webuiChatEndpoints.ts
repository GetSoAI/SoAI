/* SoAI - WebUI chat API endpoint factory [frontend/assets/ts/core/api/endpoints/webuiChatEndpoints.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import { decodeNoContentResponse } from '@core/api/contracts/noContentContract.ts';
import type { OpaqueJsonObject } from '@core/api/contracts/opaquePayload.ts';
import { CONVERSATION_HISTORY_REQUEST_TIMEOUT_MS } from '@core/api/conversationHistoryTimeout.ts';
import { buildQueryRequestOptions } from '@core/api/requestOptions.ts';
import type { ApiQueryParameters, RequestOptions } from '@core/api/types/request.ts';
import { decodeArchivedPageResponse, decodeArchivedSearchResponse, decodeConversationBatchDeleteResponse, decodeConversationDeleteAllResponse, decodeConversationListResponse, decodeConversationResponse, type ArchivedConversationsPageResponse, type ArchivedConversationResponse, type ConversationBatchDeleteResponse, type ConversationDeleteAllResponse, type ConversationMessageSyncCursorResponse, type ConversationMessageWindowResponse, type ConversationMessageWriteResponse, type ConversationRunningActivityResponse, type WebuiConversationResponse } from '@core/api/contracts/webuiConversationContracts.ts';
import { createWebuiChatAttachmentEndpoints, type WebuiChatAttachmentEndpoints } from '@core/api/endpoints/webuiChatAttachmentEndpoints.ts';
import { createWebuiConversationPaths } from '@core/api/endpoints/webuiConversationPaths.ts';
import { createWebuiChatInteractionEndpoints, type WebuiChatInteractionEndpoints } from '@core/api/endpoints/webuiChatInteractionEndpoints.ts';
import { createAgentEndpoints, type WebuiAgentEndpoints } from '@core/api/endpoints/webuiChatAgentEndpoints.ts';
import { createDraftEndpoints, type WebuiChatDraftEndpoints } from '@core/api/endpoints/webuiChatDraftEndpoints.ts';
import { createInputQueueEndpoints, type WebuiInputQueueEndpoints } from '@core/api/endpoints/webuiChatInputQueueEndpoints.ts';
import { createChatPromptHistoryEndpoints, type WebuiChatPromptHistoryEndpoints } from '@core/api/endpoints/webuiChatPromptHistoryEndpoints.ts';
import { createWebuiChatPresetEndpoints, type WebuiChatPresetEndpoints } from '@core/api/endpoints/webuiChatPresetEndpoints.ts';
import { createRagEndpoints, type WebuiRagEndpoints } from '@core/api/endpoints/webuiChatRagEndpoints.ts';
import { decodeFileExplorerBrowseResponse } from '@core/api/contracts/fileExplorerContracts.ts';
import type { FileExplorerListResponse, FileExplorerSearchResponse } from '@core/api/contracts/fileExplorerContractTypes.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { decodeMessageSyncCursorResponse, decodeMessageWindowResponse, decodeMessageWriteResponse, decodeRunningActivityResponse } from '@core/api/contracts/webuiMessageEnvelopeContracts.ts';
import {
    decodeComparisonTurnPreflight,
    decodeMcpConfig,
    decodeMcpToolCatalog,
    decodePdfExportAccepted,
    decodeRawResponse,
    decodeSearchConfig,
    decodeSoaiLinkResolve,
    decodeSoaiOpen,
    decodeSoaiPreview,
    decodeSoaiRead,
    decodeSoaiToken,
    decodeStreamStatus,
    decodeWorkspacePathConfig,
    type ComparisonTurnPreflightRequest,
    type ComparisonTurnPreflightResponse,
    type ConversationJsonExportRequest,
    type ConversationMcpConfigResponse,
    type ConversationMcpConfigUpdateRequest,
    type ConversationMcpToolCatalogResponse,
    type ConversationPdfExportAcceptedResponse,
    type ConversationPdfExportStartRequest,
    type ConversationSearchConfigResponse,
    type ConversationSearchConfigUpdateRequest,
    type ConversationStreamStatusResponse,
    type ConversationWorkspacePathConfigResponse,
    type ConversationWorkspacePathConfigUpdateRequest,
    type SoaiLinkResolveRequest,
    type SoaiLinkResolveResponse,
    type SoaiPathOpenResponse,
    type SoaiPathOperationRequest,
    type SoaiPathPreviewResponse,
    type SoaiPathReadResponse,
    type SoaiPathTokenResponse
} from '@core/api/contracts/webuiChatOperationContracts.ts';
import { decodeMessageResponse, type WebuiConversationMessageResponse } from '@core/api/contracts/webuiMessageContracts.ts';
import { serializeMcpConfigUpdate, serializeSearchConfigUpdate, serializeWorkspacePathConfigUpdate } from '@core/api/contracts/webuiChatConfigurationSerialization.ts';
import { serializeSoaiLinkResolveRequest, serializeSoaiPathBrowseRequest, serializeSoaiPathOperationRequest } from '@core/api/contracts/webuiSoaiPathSerialization.ts';
import { serializeComparisonTurnPreflight, serializeConversationJsonExport, serializeConversationPdfExportStart } from '@core/api/contracts/webuiChatOperationSerialization.ts';
import { serializeConversationArchivedRequest, serializeConversationBatchDeleteRequest, serializeConversationCloneRequest, serializeConversationColorRequest, serializeConversationCreateRequest, serializeConversationFavoriteRequest, serializeConversationSettingsRequest, serializeConversationTitleRequest, type ConversationCloneRequest, type ConversationCreateRequest } from '@core/api/contracts/webuiConversationRequestContracts.ts';
import { serializeMessageResubmitRequest, serializeMessageTargetMutationRequest, serializeMessageWriteRequest, type MessageResubmitRequest, type MessageTargetMutationRequest } from '@core/api/contracts/webuiMessageMutationContracts.ts';

interface WebuiChatEndpoints {
    chat: {
        list(): Promise<WebuiConversationResponse[]>;
        create(payload: ConversationCreateRequest, options?: RequestOptions): Promise<WebuiConversationResponse>;
        clone(id: string, payload: ConversationCloneRequest): Promise<WebuiConversationResponse>;
        get(id: string): Promise<WebuiConversationResponse>;
        delete(id: string): Promise<void>;
        batchDelete(ids: readonly string[]): Promise<ConversationBatchDeleteResponse>;
        deleteAll(): Promise<ConversationDeleteAllResponse>;
        interactions: WebuiChatInteractionEndpoints;
        messages: WebuiChatMessageEndpoints;
        attachments: WebuiChatAttachmentEndpoints;
        assistantMessages: WebuiAssistantMessageEndpoints;
        soaiLinks: WebuiSoaiLinksEndpoints;
        soaiPaths: WebuiSoaiPathsEndpoints;
        streamStatus: WebuiConversationStreamStatusEndpoints;
        comparisonTurns: WebuiComparisonTurnEndpoints;
        updateTitle(id: string, title: string): Promise<WebuiConversationResponse>;
        updateSettings(id: string, settings: OpaqueJsonObject): Promise<WebuiConversationResponse>;
        updateColor(id: string, color: string | null): Promise<WebuiConversationResponse>;
        updateFavorite(id: string, isFavorite: boolean): Promise<WebuiConversationResponse>;
        updateArchived(id: string, isArchived: boolean): Promise<WebuiConversationResponse>;
        listArchived(options?: ArchivedConversationListOptions | null, requestOptions?: RequestOptions): Promise<ArchivedConversationsPageResponse>;
        searchArchived(options?: ApiQueryParameters | null, requestOptions?: RequestOptions): Promise<ArchivedConversationResponse[]>;
        workspacePath: WebuiWorkspacePathEndpoints;
        agent: WebuiAgentEndpoints;
        inputQueue: WebuiInputQueueEndpoints;
        promptHistory: WebuiChatPromptHistoryEndpoints;
        presets: WebuiChatPresetEndpoints;
        draft: WebuiChatDraftEndpoints;
        rag: WebuiRagEndpoints;
        search: WebuiSearchEndpoints;
        mcp: WebuiMcpConversationEndpoints;
        exportPdf: WebuiConversationPdfExportEndpoints;
        exportJson: WebuiConversationJsonExportEndpoints;
    };
}

interface ArchivedConversationListOptions {
    limit?: number;
    beforeLastModifiedAtMs?: number | undefined;
    beforeId?: string | undefined;
}

const serializeArchivedConversationListOptions = (options: ArchivedConversationListOptions | null): ApiQueryParameters | null =>
    options === null
        ? null
        : {
              limit: options.limit,
              'before_last_modified_at_ms': options.beforeLastModifiedAtMs,
              'before_id': options.beforeId
          };

interface WebuiChatMessageEndpoints {
    window(id: string, options: ApiQueryParameters, requestOptions?: RequestOptions): Promise<ConversationMessageWindowResponse>;
    runningActivity(id: string, requestOptions?: RequestOptions): Promise<ConversationRunningActivityResponse>;
    replace(id: string, messages: JsonValue, expectedLastModifiedAtMs: number): Promise<ConversationMessageWriteResponse>;
    append(id: string, messages: JsonValue, expectedLastModifiedAtMs: number): Promise<ConversationMessageWriteResponse>;
    resubmit(id: string, payload: MessageResubmitRequest): Promise<ConversationMessageWriteResponse>;
    truncate(id: string, payload: MessageTargetMutationRequest): Promise<ConversationMessageWriteResponse>;
    deleteMessage(id: string, payload: MessageTargetMutationRequest): Promise<ConversationMessageWriteResponse>;
    syncCursor(id: string): Promise<ConversationMessageSyncCursorResponse>;
}

interface WebuiAssistantMessageEndpoints {
    streamState(id: string, assistantTurnAtMs: number, modelVariantIndex: number, options?: RequestOptions): Promise<WebuiConversationMessageResponse>;
}

interface WebuiSoaiLinksEndpoints {
    resolve(id: string, payload: SoaiLinkResolveRequest, options?: RequestOptions): Promise<SoaiLinkResolveResponse>;
}

interface WebuiSoaiPathsEndpoints {
    browse(id: string, payload: WebuiSoaiPathBrowseRequest, options?: RequestOptions): Promise<FileExplorerListResponse | FileExplorerSearchResponse>;
    preview(id: string, payload: SoaiPathOperationRequest, options?: RequestOptions): Promise<SoaiPathPreviewResponse>;
    read(id: string, payload: SoaiPathOperationRequest, options?: RequestOptions): Promise<SoaiPathReadResponse>;
    download(id: string, payload: SoaiPathOperationRequest, options?: RequestOptions): Promise<Response | { state: 'unavailable' }>;
    open(id: string, payload: SoaiPathOperationRequest, options?: RequestOptions): Promise<SoaiPathOpenResponse>;
    token(id: string, payload: SoaiPathOperationRequest, options?: RequestOptions): Promise<SoaiPathTokenResponse>;
}

interface WebuiSoaiPathBrowseRequest {
    query: string | null;
    limit: number;
}

interface WebuiConversationStreamStatusEndpoints {
    get(id: string, options?: RequestOptions): Promise<ConversationStreamStatusResponse>;
}

interface WebuiComparisonTurnEndpoints {
    preflight(id: string, request: ComparisonTurnPreflightRequest): Promise<ComparisonTurnPreflightResponse>;
}

interface WebuiWorkspacePathEndpoints {
    getConfig(id: string, options?: RequestOptions): Promise<ConversationWorkspacePathConfigResponse>;
    updateConfig(id: string, payload: ConversationWorkspacePathConfigUpdateRequest): Promise<ConversationWorkspacePathConfigResponse>;
}

interface WebuiSearchEndpoints {
    getConfig(id: string, options?: RequestOptions): Promise<ConversationSearchConfigResponse>;
    updateConfig(id: string, payload: ConversationSearchConfigUpdateRequest): Promise<ConversationSearchConfigResponse>;
}

interface WebuiMcpConversationEndpoints {
    getTools(id: string, options?: RequestOptions): Promise<ConversationMcpToolCatalogResponse>;
    getConfig(id: string, options?: RequestOptions): Promise<ConversationMcpConfigResponse>;
    updateConfig(id: string, payload: ConversationMcpConfigUpdateRequest): Promise<ConversationMcpConfigResponse>;
}

interface WebuiConversationPdfExportEndpoints {
    start(file: Blob, request: ConversationPdfExportStartRequest, options?: RequestOptions): Promise<ConversationPdfExportAcceptedResponse>;
    download(taskId: string, options?: RequestOptions): Promise<Response>;
}

interface WebuiConversationJsonExportEndpoints {
    download(id: string, request: ConversationJsonExportRequest, options?: RequestOptions): Promise<Response>;
}

const createWebuiChatEndpoints = (api: ApiClientContext): WebuiChatEndpoints => {
    const paths = createWebuiConversationPaths(api);
    return {
        chat: {
            list: async (): Promise<WebuiConversationResponse[]> => decodeConversationListResponse(await api.get('/api/v1/webui/conversations')),
            create: async (payload, options = {}): Promise<WebuiConversationResponse> => decodeConversationResponse(await api.post('/api/v1/webui/conversations', serializeConversationCreateRequest(payload), options)),
            clone: async (id, payload): Promise<WebuiConversationResponse> => decodeConversationResponse(await api.post(paths.clone(id), serializeConversationCloneRequest(payload))),
            get: async (id): Promise<WebuiConversationResponse> => decodeConversationResponse(await api.get(paths.base(id))),
            delete: async (id): Promise<void> => {
                decodeNoContentResponse(await api.delete(paths.base(id)), 'Conversation delete response');
            },
            batchDelete: async (ids): Promise<ConversationBatchDeleteResponse> => decodeConversationBatchDeleteResponse(await api.post('/api/v1/webui/conversations/batch-delete', serializeConversationBatchDeleteRequest(ids))),
            deleteAll: async (): Promise<ConversationDeleteAllResponse> => decodeConversationDeleteAllResponse(await api.delete('/api/v1/webui/conversations')),
            interactions: createWebuiChatInteractionEndpoints(api, paths),
            messages: {
                window: async (id, options, requestOptions = {}): Promise<ConversationMessageWindowResponse> => decodeMessageWindowResponse(await api.get(paths.messageWindow(id), { timeoutMs: CONVERSATION_HISTORY_REQUEST_TIMEOUT_MS, ...buildQueryRequestOptions(options), ...requestOptions })),
                runningActivity: async (id, requestOptions = {}): Promise<ConversationRunningActivityResponse> => decodeRunningActivityResponse(await api.get(paths.messageRunningActivity(id), requestOptions)),
                replace: async (id, messages, expectedLastModifiedAtMs): Promise<ConversationMessageWriteResponse> => decodeMessageWriteResponse(await api.put(paths.messages(id), serializeMessageWriteRequest(messages, expectedLastModifiedAtMs))),
                append: async (id, messages, expectedLastModifiedAtMs): Promise<ConversationMessageWriteResponse> => decodeMessageWriteResponse(await api.post(paths.messages(id), serializeMessageWriteRequest(messages, expectedLastModifiedAtMs))),
                resubmit: async (id, payload): Promise<ConversationMessageWriteResponse> => decodeMessageWriteResponse(await api.post(paths.messageResubmit(id), serializeMessageResubmitRequest(payload))),
                truncate: async (id, payload): Promise<ConversationMessageWriteResponse> => decodeMessageWriteResponse(await api.post(paths.messageTruncate(id), serializeMessageTargetMutationRequest(payload))),
                deleteMessage: async (id, payload): Promise<ConversationMessageWriteResponse> => decodeMessageWriteResponse(await api.post(paths.messageDelete(id), serializeMessageTargetMutationRequest(payload))),
                syncCursor: async (id): Promise<ConversationMessageSyncCursorResponse> => decodeMessageSyncCursorResponse(await api.get(paths.messageSyncCursor(id)))
            },
            attachments: createWebuiChatAttachmentEndpoints(api, paths),
            assistantMessages: {
                streamState: async (id, assistantTurnAtMs, modelVariantIndex, options = {}): Promise<WebuiConversationMessageResponse> => decodeMessageResponse(await api.get(paths.assistantTurnStreamState(id, assistantTurnAtMs, modelVariantIndex), options), 'Assistant stream state response')
            },
            soaiLinks: {
                resolve: async (id, payload, options = {}): Promise<SoaiLinkResolveResponse> => decodeSoaiLinkResolve(await api.post(paths.soaiLinksResolve(id), serializeSoaiLinkResolveRequest(payload), options))
            },
            soaiPaths: {
                browse: async (id, payload, options = {}): Promise<FileExplorerListResponse | FileExplorerSearchResponse> => {
                    return decodeFileExplorerBrowseResponse(await api.post(paths.soaiPathsBrowse(id), serializeSoaiPathBrowseRequest(payload), options), payload.query !== null);
                },
                preview: async (id, payload, options = {}): Promise<SoaiPathPreviewResponse> => decodeSoaiPreview(await api.post(paths.soaiPathsPreview(id), serializeSoaiPathOperationRequest(payload), options)),
                read: async (id, payload, options = {}): Promise<SoaiPathReadResponse> => decodeSoaiRead(await api.post(paths.soaiPathsRead(id), serializeSoaiPathOperationRequest(payload), options)),
                download: async (id, payload, options = {}): Promise<Response | { state: 'unavailable' }> => (options.rawResponse === true ? decodeRawResponse(await api.post(paths.soaiPathsDownload(id), serializeSoaiPathOperationRequest(payload), options), 'SoAI path download response') : { state: 'unavailable' }),
                open: async (id, payload, options = {}): Promise<SoaiPathOpenResponse> => decodeSoaiOpen(await api.post(paths.soaiPathsOpen(id), serializeSoaiPathOperationRequest(payload), options)),
                token: async (id, payload, options = {}): Promise<SoaiPathTokenResponse> => decodeSoaiToken(await api.post(paths.soaiPathsToken(id), serializeSoaiPathOperationRequest(payload), options))
            },
            streamStatus: {
                get: async (id, options = {}): Promise<ConversationStreamStatusResponse> => decodeStreamStatus(await api.get(paths.streamStatus(id), options))
            },
            comparisonTurns: {
                preflight: async (id, request): Promise<ComparisonTurnPreflightResponse> => decodeComparisonTurnPreflight(await api.post(paths.comparisonPreflight(id), serializeComparisonTurnPreflight(request)))
            },
            updateTitle: async (id, title): Promise<WebuiConversationResponse> => decodeConversationResponse(await api.patch(paths.title(id), serializeConversationTitleRequest(title))),
            updateSettings: async (id, settings): Promise<WebuiConversationResponse> => decodeConversationResponse(await api.patch(paths.settings(id), serializeConversationSettingsRequest(settings))),
            updateColor: async (id, color): Promise<WebuiConversationResponse> => decodeConversationResponse(await api.patch(paths.color(id), serializeConversationColorRequest(color))),
            updateFavorite: async (id, isFavorite): Promise<WebuiConversationResponse> => decodeConversationResponse(await api.patch(paths.favorite(id), serializeConversationFavoriteRequest(isFavorite))),
            updateArchived: async (id, isArchived): Promise<WebuiConversationResponse> => decodeConversationResponse(await api.patch(paths.archived(id), serializeConversationArchivedRequest(isArchived))),
            listArchived: async (options = null, requestOptions = {}): Promise<ArchivedConversationsPageResponse> => decodeArchivedPageResponse(await api.get(paths.archivedList(), { ...buildQueryRequestOptions(serializeArchivedConversationListOptions(options)), ...requestOptions })),
            searchArchived: async (options = null, requestOptions = {}): Promise<ArchivedConversationResponse[]> => decodeArchivedSearchResponse(await api.get(paths.archivedSearch(), { ...buildQueryRequestOptions(options), ...requestOptions })),
            workspacePath: {
                getConfig: async (id, options = {}): Promise<ConversationWorkspacePathConfigResponse> => decodeWorkspacePathConfig(await api.get(paths.workspacePath(id), options)),
                updateConfig: async (id, payload): Promise<ConversationWorkspacePathConfigResponse> => decodeWorkspacePathConfig(await api.patch(paths.workspacePath(id), serializeWorkspacePathConfigUpdate(payload)))
            },
            agent: createAgentEndpoints(api, paths),
            inputQueue: createInputQueueEndpoints(api, paths),
            promptHistory: createChatPromptHistoryEndpoints(api),
            presets: createWebuiChatPresetEndpoints(api),
            draft: createDraftEndpoints(api, paths),
            rag: createRagEndpoints(api, paths),
            search: {
                getConfig: async (id, options = {}): Promise<ConversationSearchConfigResponse> => decodeSearchConfig(await api.get(paths.searchConfig(id), options)),
                updateConfig: async (id, payload): Promise<ConversationSearchConfigResponse> => decodeSearchConfig(await api.patch(paths.searchConfig(id), serializeSearchConfigUpdate(payload)))
            },
            mcp: {
                getTools: async (id, options = {}): Promise<ConversationMcpToolCatalogResponse> => decodeMcpToolCatalog(await api.get(paths.mcpTools(id), options)),
                getConfig: async (id, options = {}): Promise<ConversationMcpConfigResponse> => decodeMcpConfig(await api.get(paths.mcpConfig(id), options)),
                updateConfig: async (id, payload): Promise<ConversationMcpConfigResponse> => decodeMcpConfig(await api.patch(paths.mcpConfig(id), serializeMcpConfigUpdate(payload)))
            },
            exportPdf: {
                start: async (file, request, options = {}): Promise<ConversationPdfExportAcceptedResponse> => decodePdfExportAccepted(await api.uploadFile('/api/v1/webui/conversations/export/pdf', file, serializeConversationPdfExportStart(request), options, 'conversation-export.html')),
                download: async (taskId, options = {}): Promise<Response> => decodeRawResponse(await api.get(`/api/v1/webui/conversations/export/pdf/${api.encodePathSegment(taskId)}/download`, { ...options, rawResponse: true }), 'Conversation PDF export download response')
            },
            exportJson: {
                download: async (id, request, options = {}): Promise<Response> => decodeRawResponse(await api.post(paths.jsonExport(id), serializeConversationJsonExport(request), { ...options, rawResponse: true }), 'Conversation JSON export download response')
            }
        }
    };
};

export { createWebuiChatEndpoints };
export type { ArchivedConversationListOptions, WebuiChatEndpoints };
