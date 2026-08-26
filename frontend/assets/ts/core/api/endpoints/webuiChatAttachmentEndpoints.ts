/* SoAI - WebUI chat attachment API endpoint factory [frontend/assets/ts/core/api/endpoints/webuiChatAttachmentEndpoints.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { WebuiConversationPaths } from '@core/api/endpoints/webuiConversationPaths.ts';
import { decodeNoContentResponse } from '@core/api/contracts/noContentContract.ts';
import { postJsonResponse } from '@core/api/jsonResponse.ts';
import { buildQueryRequestOptions, buildSignalRequestOptions, type SignalOptions } from '@core/api/requestOptions.ts';
import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import type { ApiQueryParameters, RequestOptions } from '@core/api/types/request.ts';
import { decodeClaim, decodeItems, decodePhysicalAttachment, decodePreview, decodeSummary, decodeSummaryCollection, decodeUse, type KnowledgeAttachmentClaimRequest, type KnowledgeAttachmentClaimResponse, type KnowledgeAttachmentCollectionResponse, type KnowledgeAttachmentItemsResponse, type KnowledgeAttachmentPreviewRequest, type KnowledgeAttachmentPreviewResponse, type KnowledgeAttachmentSummary, type KnowledgeAttachmentUseRequest, type KnowledgeAttachmentUseResponse, type PhysicalAttachmentResponse } from '@core/api/contracts/webuiAttachmentContracts.ts';
import { serializeKnowledgeAttachmentClaimRequest, serializeKnowledgeAttachmentPreviewRequest, serializeKnowledgeAttachmentUseRequest } from '@core/api/contracts/webuiAttachmentSerialization.ts';
import { FILE_TRANSFER_REQUEST_TIMEOUT_MS } from '@core/api/fileTransferTimeout.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

interface WebuiChatAttachmentEndpoints {
    stage(conversationId: string, payload: WebuiChatAttachmentStagePayload, options?: RequestOptions): Promise<PhysicalAttachmentResponse>;
    get(conversationId: string, attachmentId: string, options?: RequestOptions): Promise<PhysicalAttachmentResponse>;
    delete(conversationId: string, attachmentId: string, options?: RequestOptions): Promise<void>;
    contentPath(conversationId: string, attachmentId: string, download: boolean): string;
    knowledge: WebuiChatKnowledgeAttachmentEndpoints;
}

interface WebuiChatKnowledgeAttachmentEndpoints {
    reusable(options?: WebuiKnowledgeReusableRequestOptions | null): Promise<KnowledgeAttachmentCollectionResponse>;
    draft(conversationId: string, options?: WebuiKnowledgeDraftRequestOptions | null): Promise<KnowledgeAttachmentCollectionResponse>;
    claim(conversationId: string, payload: KnowledgeAttachmentClaimRequest, options?: RequestOptions): Promise<KnowledgeAttachmentClaimResponse>;
    get(conversationId: string, knowledgeAttachmentId: string, options?: RequestOptions): Promise<KnowledgeAttachmentSummary>;
    delete(conversationId: string, knowledgeAttachmentId: string, options?: RequestOptions): Promise<KnowledgeAttachmentSummary>;
    cancel(conversationId: string, knowledgeAttachmentId: string, options?: RequestOptions): Promise<KnowledgeAttachmentSummary>;
    items(conversationId: string, knowledgeAttachmentId: string, options?: WebuiKnowledgeItemsRequestOptions | null): Promise<KnowledgeAttachmentItemsResponse>;
    previewItem(conversationId: string, knowledgeAttachmentId: string, itemId: string, payload: KnowledgeAttachmentPreviewRequest, options?: RequestOptions): Promise<KnowledgeAttachmentPreviewResponse>;
    useItems(conversationId: string, payload: KnowledgeAttachmentUseRequest, options?: RequestOptions): Promise<KnowledgeAttachmentUseResponse>;
}

interface WebuiKnowledgeDraftRequestOptions extends SignalOptions {
    previewLimit?: number;
}

interface WebuiKnowledgeReusableRequestOptions extends SignalOptions {
    query?: string | undefined;
    limit?: number | undefined;
}

interface WebuiKnowledgeItemsRequestOptions extends SignalOptions {
    limit?: number | undefined;
    cursorItemIndex?: number | undefined;
    cursorId?: number | undefined;
    status?: string | undefined;
    query?: string | undefined;
}

interface WebuiChatAttachmentStagePayload {
    file: File;
    displayName: string;
    source: string;
    clientAttachmentId: string;
    clientRequestId: string;
}

const buildReusableKnowledgePayload = (options: WebuiKnowledgeReusableRequestOptions | null): JsonObject => {
    if (options === null) {
        return {};
    }
    const payload: JsonObject = {};
    if (options['query'] !== undefined) {
        payload['query'] = options['query'];
    }
    if (options['limit'] !== undefined) {
        payload['limit'] = options['limit'];
    }
    return payload;
};

const buildKnowledgeItemsPayload = (options: WebuiKnowledgeItemsRequestOptions | null): JsonObject => {
    if (options === null) {
        return {};
    }
    const payload: JsonObject = {};
    if (options['limit'] !== undefined) {
        payload['limit'] = options['limit'];
    }
    if (options.cursorItemIndex !== undefined) {
        payload['cursor_item_index'] = options.cursorItemIndex;
    }
    if (options.cursorId !== undefined) {
        payload['cursor_id'] = options.cursorId;
    }
    if (options['status'] !== undefined) {
        payload['status'] = options['status'];
    }
    if (options['query'] !== undefined) {
        payload['query'] = options['query'];
    }
    return payload;
};

const buildKnowledgeDraftRequestOptions = (options: WebuiKnowledgeDraftRequestOptions | null): RequestOptions => {
    if (options === null) {
        return buildQueryRequestOptions(null);
    }
    const query: ApiQueryParameters = {};
    if (options.previewLimit !== undefined) {
        query['preview_limit'] = options.previewLimit;
    }
    return buildQueryRequestOptions(query, options.signal);
};

const createWebuiChatAttachmentEndpoints = (api: ApiClientContext, paths: WebuiConversationPaths): WebuiChatAttachmentEndpoints => {
    return {
        stage: async (conversationId, payload, options = {}): Promise<PhysicalAttachmentResponse> => {
            if (!(payload.file instanceof File)) {
                throw new Error('webui.chat.attachments.stage requires a File');
            }
            const formData = new FormData();
            formData.append('file', payload.file, payload.file.name);
            formData.append('display_name', payload.displayName);
            formData.append('source', payload.source);
            formData.append('client_attachment_id', payload.clientAttachmentId);
            formData.append('client_request_id', payload.clientRequestId);
            return decodePhysicalAttachment(
                await api.post(paths.attachments(conversationId), formData, {
                    ...options,
                    headers: {},
                    timeoutMs: FILE_TRANSFER_REQUEST_TIMEOUT_MS
                })
            );
        },
        get: async (conversationId, attachmentId, options = {}): Promise<PhysicalAttachmentResponse> => decodePhysicalAttachment(await api.get(paths.attachment(conversationId, attachmentId), options)),
        delete: async (conversationId, attachmentId, options = {}): Promise<void> => decodeNoContentResponse(await api.delete(paths.attachment(conversationId, attachmentId), options), 'Physical attachment delete response'),
        contentPath: (conversationId, attachmentId, download): string => paths.attachmentContent(conversationId, attachmentId, download),
        knowledge: {
            reusable: async (options = null): Promise<KnowledgeAttachmentCollectionResponse> => decodeSummaryCollection(await api.post('/api/v1/webui/knowledge-attachments/reusable', buildReusableKnowledgePayload(options), buildSignalRequestOptions(options ?? {}))),
            draft: async (conversationId, options = null): Promise<KnowledgeAttachmentCollectionResponse> => decodeSummaryCollection(await api.get(paths.knowledgeAttachmentsDraft(conversationId), buildKnowledgeDraftRequestOptions(options))),
            claim: async (conversationId, payload, options = {}): Promise<KnowledgeAttachmentClaimResponse> => decodeClaim(await api.post(paths.knowledgeAttachmentsClaim(conversationId), serializeKnowledgeAttachmentClaimRequest(payload), options)),
            get: async (conversationId, knowledgeAttachmentId, options = {}): Promise<KnowledgeAttachmentSummary> => decodeSummary(await api.get(paths.knowledgeAttachment(conversationId, knowledgeAttachmentId), options)),
            delete: async (conversationId, knowledgeAttachmentId, options = {}): Promise<KnowledgeAttachmentSummary> => decodeSummary(await api.delete(paths.knowledgeAttachment(conversationId, knowledgeAttachmentId), options)),
            cancel: async (conversationId, knowledgeAttachmentId, options = {}): Promise<KnowledgeAttachmentSummary> => decodeSummary(await postJsonResponse(api, paths.knowledgeAttachmentCancel(conversationId, knowledgeAttachmentId), null, options)),
            items: async (conversationId, knowledgeAttachmentId, options = null): Promise<KnowledgeAttachmentItemsResponse> => decodeItems(await api.post(paths.knowledgeAttachmentItemsQuery(conversationId, knowledgeAttachmentId), buildKnowledgeItemsPayload(options), buildSignalRequestOptions(options ?? {}))),
            previewItem: async (conversationId, knowledgeAttachmentId, itemId, payload, options = {}): Promise<KnowledgeAttachmentPreviewResponse> => decodePreview(await api.post(paths.knowledgeAttachmentItemPreview(conversationId, knowledgeAttachmentId, itemId), serializeKnowledgeAttachmentPreviewRequest(payload), options)),
            useItems: async (conversationId, payload, options = {}): Promise<KnowledgeAttachmentUseResponse> => decodeUse(await api.post(paths.knowledgeAttachmentsUse(conversationId), serializeKnowledgeAttachmentUseRequest(payload), options))
        }
    };
};

export { createWebuiChatAttachmentEndpoints };
export type { WebuiChatAttachmentEndpoints };
