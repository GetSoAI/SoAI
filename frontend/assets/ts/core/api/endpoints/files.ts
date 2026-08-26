/* SoAI - Shared API files [frontend/assets/ts/core/api/endpoints/files.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import { decodeFileContentResponse, decodeFileDeleteResponse, decodeFileListResponse, decodeFileObject, type OpenAiFileDeleteResponse, type OpenAiFileListResponse, type OpenAiFileObject } from '@core/api/contracts/fileContracts.ts';

const createFilesEndpoints = (api: ApiClientContext): { upload: (file: Blob, data?: Record<string, string | Blob>) => Promise<OpenAiFileObject>; list: () => Promise<OpenAiFileListResponse>; retrieve: (id: string) => Promise<OpenAiFileObject>; download: (id: string) => Promise<Response>; delete: (id: string) => Promise<OpenAiFileDeleteResponse> } => {
    return {
        upload: async (file: Blob, data: Record<string, string | Blob> = {}): Promise<OpenAiFileObject> => decodeFileObject(await api.uploadFile('/v1/files', file, data)),
        list: async (): Promise<OpenAiFileListResponse> => decodeFileListResponse(await api.get('/v1/files')),
        retrieve: async (id: string): Promise<OpenAiFileObject> => decodeFileObject(await api.get(`/v1/files/${api.encodePathSegment(id)}`)),
        download: async (id: string): Promise<Response> => decodeFileContentResponse(await api.get(`/v1/files/${api.encodePathSegment(id)}/content`, { rawResponse: true })),
        delete: async (id: string): Promise<OpenAiFileDeleteResponse> => decodeFileDeleteResponse(await api.delete(`/v1/files/${api.encodePathSegment(id)}`))
    };
};

export { createFilesEndpoints };
