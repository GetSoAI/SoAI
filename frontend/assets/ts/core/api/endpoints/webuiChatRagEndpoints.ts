/* SoAI - WebUI chat RAG API endpoint factory [frontend/assets/ts/core/api/endpoints/webuiChatRagEndpoints.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createRagBatchUploadPayload, createRagSingleUploadPayload, type RagBatchUploadOptions } from '@core/api/endpoints/webuiRagUploads.ts';
import { getJsonResponse, patchJsonResponse, requireJsonResponse } from '@core/api/jsonResponse.ts';
import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import { decodeRagBatch, decodeRagConfig, decodeRagDelete, decodeRagDocuments, decodeRagIngest, decodeRagReindex, decodeRagUpload, serializeRagConfigUpdateRequest, type RagBatchUploadResponse, type RagConfigResponse, type RagConfigUpdateRequest, type RagDeleteResponse, type RagDocumentsResponse, type RagIngestResponse, type RagReindexResponse, type RagUploadResponse } from '@core/api/contracts/webuiRagContracts.ts';
import type { RequestOptions } from '@core/api/types/request.ts';
import type { WebuiConversationPaths } from '@core/api/endpoints/webuiConversationPaths.ts';

interface WebuiRagEndpoints {
    getConfig(id: string, options?: RequestOptions): Promise<RagConfigResponse>;
    updateConfig(id: string, payload: RagConfigUpdateRequest): Promise<RagConfigResponse>;
    listDocuments(id: string, options?: ({ limit?: number; offset?: number; includeDocuments?: boolean } & RequestOptions) | null): Promise<RagDocumentsResponse>;
    uploadDocument(id: string, file: File): Promise<RagUploadResponse>;
    uploadDocumentsBatch(id: string, files: readonly File[], options?: RagBatchUploadOptions): Promise<RagBatchUploadResponse>;
    ingestFileExplorer(id: string, payload: { path: string; recursive?: boolean }, options?: RequestOptions): Promise<RagIngestResponse>;
    deleteDocument(id: string, documentId: string, options?: RequestOptions): Promise<RagDeleteResponse>;
    reindex(id: string, embeddingModel: string, options?: RequestOptions): Promise<RagReindexResponse>;
}

const createRagEndpoints = (api: ApiClientContext, paths: WebuiConversationPaths): WebuiRagEndpoints => {
    return {
        getConfig: async (id, options = {}): Promise<RagConfigResponse> => decodeRagConfig(await getJsonResponse(api, paths.ragConfig(id), options)),
        updateConfig: async (id, payload): Promise<RagConfigResponse> => decodeRagConfig(await patchJsonResponse(api, paths.ragConfig(id), serializeRagConfigUpdateRequest(payload))),
        listDocuments: async (id, options = null): Promise<RagDocumentsResponse> => decodeRagDocuments(await getJsonResponse(api, paths.ragDocuments(id), { signal: options?.signal, query: options ? { limit: options.limit, offset: options.offset, 'include_documents': options.includeDocuments } : null })),
        uploadDocument: async (id, file): Promise<RagUploadResponse> => {
            const payload = createRagSingleUploadPayload(file);
            return decodeRagUpload(await api.uploadFile(paths.ragDocuments(id), file, payload.additionalData, payload.options, payload.filenameOverride));
        },
        uploadDocumentsBatch: async (id, files, options = {}): Promise<RagBatchUploadResponse> => {
            const payload = createRagBatchUploadPayload(files, options);
            return decodeRagBatch(await requireJsonResponse(api.post(paths.ragDocumentsBatch(id), payload.formData, payload.options), 'POST', paths.ragDocumentsBatch(id)));
        },
        ingestFileExplorer: async (id, payload, options = {}): Promise<RagIngestResponse> => decodeRagIngest(await api.post(paths.ragIngestFileExplorer(id), payload, options)),
        deleteDocument: async (id, documentId, options = {}): Promise<RagDeleteResponse> => decodeRagDelete(await api.delete(paths.ragDocument(id, documentId), options)),
        reindex: async (id, embeddingModel, options = {}): Promise<RagReindexResponse> => decodeRagReindex(await api.post(paths.ragReindex(id), undefined, { ...options, query: { 'embedding_model': embeddingModel } }))
    };
};

export { createRagEndpoints };
export type { WebuiRagEndpoints };
