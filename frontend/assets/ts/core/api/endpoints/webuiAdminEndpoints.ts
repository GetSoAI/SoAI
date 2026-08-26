/* SoAI - Shared API WebUI admin endpoints [frontend/assets/ts/core/api/endpoints/webuiAdminEndpoints.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import { FILE_TRANSFER_REQUEST_TIMEOUT_MS } from '@core/api/fileTransferTimeout.ts';
import { decodeBackupExportResponse, decodeBackupListResponse, decodeBackupTaskAcceptedResponse, decodeFactoryResetResponse, type BackupListEntry, type BackupListResponse, type BackupTaskAcceptedResponse, type FactoryResetResponse } from '@core/api/contracts/adminContracts.ts';
import { decodeApplicationRestartResponse, type ApplicationRestartResponse } from '@core/api/contracts/powerContracts.ts';

interface WebuiAdminEndpoints {
    admin: {
        resetConfiguration(): Promise<ApplicationRestartResponse>;
        factoryReset(): Promise<FactoryResetResponse>;
        backups: {
            list(): Promise<BackupListResponse>;
            create(): Promise<BackupTaskAcceptedResponse>;
            restore(backupId: string): Promise<BackupTaskAcceptedResponse>;
            verify(backupId: string): Promise<BackupTaskAcceptedResponse>;
            remove(backupId: string): Promise<BackupTaskAcceptedResponse>;
            export(backupId: string): Promise<Response>;
            exportUrl(backupId: string): string;
        };
    };
}

const createWebuiAdminEndpoints = (api: ApiClientContext): WebuiAdminEndpoints => ({
    admin: {
        resetConfiguration: async (): Promise<ApplicationRestartResponse> => decodeApplicationRestartResponse(await api.post('/api/v1/system/admin/configuration/reset')),
        factoryReset: async (): Promise<FactoryResetResponse> => decodeFactoryResetResponse(await api.post('/api/v1/system/admin/factory-reset')),
        backups: {
            list: async (): Promise<BackupListResponse> => decodeBackupListResponse(await api.get('/api/v1/backups')),
            create: async (): Promise<BackupTaskAcceptedResponse> => decodeBackupTaskAcceptedResponse(await api.post('/api/v1/backups')),
            restore: async (backupId): Promise<BackupTaskAcceptedResponse> => decodeBackupTaskAcceptedResponse(await api.post(`/api/v1/backups/${api.encodePathSegment(backupId)}/restore`)),
            verify: async (backupId): Promise<BackupTaskAcceptedResponse> => decodeBackupTaskAcceptedResponse(await api.post(`/api/v1/backups/${api.encodePathSegment(backupId)}/verify`)),
            remove: async (backupId): Promise<BackupTaskAcceptedResponse> => decodeBackupTaskAcceptedResponse(await api.delete(`/api/v1/backups/${api.encodePathSegment(backupId)}`)),
            export: async (backupId): Promise<Response> => decodeBackupExportResponse(await api.get(`/api/v1/backups/${api.encodePathSegment(backupId)}/export`, { rawResponse: true, timeoutMs: FILE_TRANSFER_REQUEST_TIMEOUT_MS })),
            exportUrl: (backupId): string => `/api/v1/backups/${encodeURIComponent(backupId)}/export`
        }
    }
});

export { createWebuiAdminEndpoints };
export type { WebuiAdminEndpoints, BackupListEntry };
