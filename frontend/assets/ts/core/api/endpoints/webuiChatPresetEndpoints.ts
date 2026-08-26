/* SoAI - WebUI chat preset endpoint owner [frontend/assets/ts/core/api/endpoints/webuiChatPresetEndpoints.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeNoContentResponse } from '@core/api/contracts/noContentContract.ts';
import { decodeChatPresetListResponse, decodeChatPresetRecord, decodeChatPresetResetResponse, serializeChatPresetCreateRequest, serializeChatPresetDeleteQuery, serializeChatPresetPathId, serializeChatPresetRenameRequest, serializeChatPresetReplaceRequest, type WebuiChatPresetCreateRequest, type WebuiChatPresetListResponse, type WebuiChatPresetRecord, type WebuiChatPresetRenameRequest, type WebuiChatPresetReplaceRequest, type WebuiChatPresetResetResponse } from '@core/api/contracts/webuiChatPresetContracts.ts';
import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import { requireJsonResponse } from '@core/api/jsonResponse.ts';
import type { RequestOptions } from '@core/api/types/request.ts';

interface WebuiChatPresetEndpoints {
    list(options?: RequestOptions): Promise<WebuiChatPresetListResponse>;
    create(request: WebuiChatPresetCreateRequest, options?: RequestOptions): Promise<WebuiChatPresetRecord>;
    rename(presetId: string, request: WebuiChatPresetRenameRequest, options?: RequestOptions): Promise<WebuiChatPresetRecord>;
    replace(presetId: string, request: WebuiChatPresetReplaceRequest, options?: RequestOptions): Promise<WebuiChatPresetRecord>;
    delete(presetId: string, expectedRevision: number, options?: RequestOptions): Promise<void>;
    reset(options?: RequestOptions): Promise<WebuiChatPresetResetResponse>;
}

const createWebuiChatPresetEndpoints = (api: ApiClientContext): WebuiChatPresetEndpoints => {
    const base = '/api/v1/webui/chat/presets';
    const itemPath = (presetId: string): string => `${base}/${api.encodePathSegment(serializeChatPresetPathId(presetId))}`;
    return {
        list: async (options = {}) => decodeChatPresetListResponse(await requireJsonResponse(api.get(base, options), 'GET', base)),
        create: async (request, options = {}) => decodeChatPresetRecord(await requireJsonResponse(api.post(base, serializeChatPresetCreateRequest(request), options), 'POST', base)),
        rename: async (presetId, request, options = {}) => decodeChatPresetRecord(await requireJsonResponse(api.patch(itemPath(presetId), serializeChatPresetRenameRequest(request), options), 'PATCH', itemPath(presetId))),
        replace: async (presetId, request, options = {}) => decodeChatPresetRecord(await requireJsonResponse(api.put(itemPath(presetId), serializeChatPresetReplaceRequest(request), options), 'PUT', itemPath(presetId))),
        delete: async (presetId, expectedRevision, options = {}) => {
            decodeNoContentResponse(await api.delete(itemPath(presetId), { ...options, query: serializeChatPresetDeleteQuery(expectedRevision) }), 'Chat preset delete response');
        },
        reset: async (options = {}) => decodeChatPresetResetResponse(await requireJsonResponse(api.delete(base, { ...options, query: { confirm: 'true' } }), 'DELETE', base))
    };
};

export { createWebuiChatPresetEndpoints };
export type { WebuiChatPresetEndpoints };
