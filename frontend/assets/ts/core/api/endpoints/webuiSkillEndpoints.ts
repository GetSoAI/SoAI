/* SoAI - Owner-private skill library endpoint owner [frontend/assets/ts/core/api/endpoints/webuiSkillEndpoints.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeBufferedFileResponse } from '@core/api/contracts/downloadContracts.ts';

import type { SkillBatchImportReceipt, SkillDetails, SkillImportReceipt, SkillLibrary, SkillSelection } from '@core/api/contracts/webuiSkillContractTypes.ts';
import { decodeSkillBatchImportReceipt, decodeSkillDetails, decodeSkillImportReceipt, decodeSkillLibrary, decodeSkillRemoval, decodeSkillSelection, requireSkillId, requireSkillIds, requireSkillRevision } from '@core/api/contracts/webuiSkillContracts.ts';
import { getJsonResponse, putJsonResponse, requireJsonResponse } from '@core/api/jsonResponse.ts';
import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import type { BufferedApiResponse } from '@core/api/bufferedResponse.ts';

import type { RequestOptions } from '@core/api/types/request.ts';

interface WebuiSkillEndpoints {
    library(options?: RequestOptions): Promise<SkillLibrary>;
    details(skillId: string, options?: RequestOptions): Promise<SkillDetails>;
    resource(skillId: string, path: string): Promise<BufferedApiResponse>;
    importSkill(file: File, uploadId: string): Promise<SkillImportReceipt>;
    importReceipt(uploadId: string, options?: RequestOptions): Promise<SkillImportReceipt>;
    importBatch(file: File, uploadId: string): Promise<SkillBatchImportReceipt>;
    importBatchReceipt(uploadId: string, options?: RequestOptions): Promise<SkillBatchImportReceipt>;
    remove(skillId: string): Promise<{ removed: boolean; revision: number }>;
    selection(conversationId: string, options?: RequestOptions): Promise<SkillSelection>;
    replaceSelection(conversationId: string, revision: number, skillIds: string[]): Promise<SkillSelection>;
}

const createWebuiSkillEndpoints = (api: ApiClientContext): WebuiSkillEndpoints => {
    const libraryPath = '/api/v1/webui/skills';
    const skillPath = (skillId: string): string => `${libraryPath}/${requireSkillId(skillId)}`;
    const selectionPath = (conversationId: string): string => `/api/v1/webui/conversations/${api.encodePathSegment(conversationId)}/skills`;
    return {
        library: async (options = {}) => decodeSkillLibrary(await getJsonResponse(api, libraryPath, options)),
        details: async (skillId, options = {}) => decodeSkillDetails(await getJsonResponse(api, skillPath(skillId), options)),
        resource: async (skillId, path) => decodeBufferedFileResponse(await api.get(`/api/v1/webui/skills/${requireSkillId(skillId)}/resources`, { query: { path }, rawResponse: true, bufferRawResponse: true })),
        importSkill: async (file, uploadId) => decodeSkillImportReceipt(await requireJsonResponse(api.uploadFile('/api/v1/webui/skills/import', file, { 'upload_id': uploadId }), 'POST', `${libraryPath}/import`)),
        importReceipt: async (uploadId, options = {}) => decodeSkillImportReceipt(await getJsonResponse(api, `${libraryPath}/imports/${api.encodePathSegment(uploadId)}`, options)),
        importBatch: async (file, uploadId) => decodeSkillBatchImportReceipt(await requireJsonResponse(api.uploadFile('/api/v1/webui/skills/import-batch', file, { 'upload_id': uploadId }), 'POST', `${libraryPath}/import-batch`)),
        importBatchReceipt: async (uploadId, options = {}) => decodeSkillBatchImportReceipt(await getJsonResponse(api, `${libraryPath}/import-batches/${api.encodePathSegment(uploadId)}`, options)),
        remove: async (skillId) => decodeSkillRemoval(await requireJsonResponse(api.delete(skillPath(skillId)), 'DELETE', skillPath(skillId))),
        selection: async (conversationId, options = {}) => decodeSkillSelection(await getJsonResponse(api, selectionPath(conversationId), options)),
        replaceSelection: async (conversationId, revision, skillIds) => decodeSkillSelection(await putJsonResponse(api, selectionPath(conversationId), { 'expected_revision': requireSkillRevision(revision), 'skill_ids': requireSkillIds(skillIds) }))
    };
};

export { createWebuiSkillEndpoints };
export type { WebuiSkillEndpoints };
