/* SoAI - Shared API software [frontend/assets/ts/core/api/endpoints/software.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeNoContentResponse } from '@core/api/contracts/noContentContract.ts';
import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import type { RequestOptions } from '@core/api/types/request.ts';
import { decodeSoftwareUpdateAcceptedResponse, decodeSoftwareUpdateCheckResponse, decodeSoftwareUpdateDiagnosticsResponse, decodeSoftwareUpdateNoticeResponse, decodeSoftwareUpdatePreparationResponse, type SoftwareUpdateAcceptedResponse, type SoftwareUpdateCheckResponse, type SoftwareUpdateDiagnostics, type SoftwareUpdateNotice, type SoftwareUpdatePreparationResponse } from '@core/api/contracts/softwareContracts.ts';
import { minutesToMs } from '@core/time/durations.ts';

interface SoftwareEndpoints {
    checkUpdates: () => Promise<SoftwareUpdateCheckResponse>;
    updateSoAI: () => Promise<SoftwareUpdateAcceptedResponse>;
    getUpdatePreparation: () => Promise<SoftwareUpdatePreparationResponse>;
    getUpdateNotice: (options?: RequestOptions) => Promise<SoftwareUpdateNotice | null>;
    acknowledgeUpdateNotice: (taskId: string, options?: RequestOptions) => Promise<void>;
    getUpdateDiagnostics: (taskId: string, options?: RequestOptions) => Promise<SoftwareUpdateDiagnostics>;
}

const createSoftwareEndpoints = (api: ApiClientContext): SoftwareEndpoints => {
    return {
        checkUpdates: async (): Promise<SoftwareUpdateCheckResponse> => decodeSoftwareUpdateCheckResponse(await api.post('/api/v1/actions/software/check-for-updates')),
        getUpdatePreparation: async (): Promise<SoftwareUpdatePreparationResponse> => decodeSoftwareUpdatePreparationResponse(await api.get('/api/v1/software/update-preparation')),
        getUpdateNotice: async (options?: RequestOptions): Promise<SoftwareUpdateNotice | null> => decodeSoftwareUpdateNoticeResponse(await api.get('/api/v1/webui/software-update-notice', options)),
        acknowledgeUpdateNotice: async (taskId: string, options?: RequestOptions): Promise<void> => decodeNoContentResponse(await api.post(`/api/v1/webui/software-update-notice/${api.encodePathSegment(taskId)}/acknowledge`, undefined, options), 'Software update notice acknowledgement response'),
        getUpdateDiagnostics: async (taskId: string, options?: RequestOptions): Promise<SoftwareUpdateDiagnostics> => decodeSoftwareUpdateDiagnosticsResponse(await api.get(`/api/v1/software/update-diagnostics/${api.encodePathSegment(taskId)}`, options), taskId),
        updateSoAI: async (): Promise<SoftwareUpdateAcceptedResponse> => decodeSoftwareUpdateAcceptedResponse(await api.post('/api/v1/software/update-soai', undefined, { timeoutMs: minutesToMs(15) }))
    };
};

export { createSoftwareEndpoints };
export type { SoftwareEndpoints };
