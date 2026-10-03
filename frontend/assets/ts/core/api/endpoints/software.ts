/* SoAI - Shared API software [frontend/assets/ts/core/api/endpoints/software.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeNoContentResponse } from '@core/api/contracts/noContentContract.ts';
import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import { decodeSoftwareUpdateAcceptedResponse, decodeSoftwareUpdateCheckResponse, decodeSoftwareUpdateNoticeResponse, decodeSoftwareUpdatePreparationResponse, type SoftwareUpdateAcceptedResponse, type SoftwareUpdateCheckResponse, type SoftwareUpdateNotice, type SoftwareUpdatePreparationResponse } from '@core/api/contracts/softwareContracts.ts';
import { minutesToMs } from '@core/time/durations.ts';

interface SoftwareEndpoints {
    checkUpdates: () => Promise<SoftwareUpdateCheckResponse>;
    updateSoAI: () => Promise<SoftwareUpdateAcceptedResponse>;
    getUpdatePreparation: () => Promise<SoftwareUpdatePreparationResponse>;
    getUpdateNotice: () => Promise<SoftwareUpdateNotice | null>;
    acknowledgeUpdateNotice: (taskId: string) => Promise<void>;
}

const createSoftwareEndpoints = (api: ApiClientContext): SoftwareEndpoints => {
    return {
        checkUpdates: async (): Promise<SoftwareUpdateCheckResponse> => decodeSoftwareUpdateCheckResponse(await api.post('/api/v1/actions/software/check-for-updates')),
        getUpdatePreparation: async (): Promise<SoftwareUpdatePreparationResponse> => decodeSoftwareUpdatePreparationResponse(await api.get('/api/v1/software/update-preparation')),
        getUpdateNotice: async (): Promise<SoftwareUpdateNotice | null> => decodeSoftwareUpdateNoticeResponse(await api.get('/api/v1/webui/software-update-notice')),
        acknowledgeUpdateNotice: async (taskId: string): Promise<void> => decodeNoContentResponse(await api.post(`/api/v1/webui/software-update-notice/${api.encodePathSegment(taskId)}/acknowledge`), 'Software update notice acknowledgement response'),
        updateSoAI: async (): Promise<SoftwareUpdateAcceptedResponse> => decodeSoftwareUpdateAcceptedResponse(await api.post('/api/v1/software/update-soai', undefined, { timeoutMs: minutesToMs(15) }))
    };
};

export { createSoftwareEndpoints };
export type { SoftwareEndpoints };
