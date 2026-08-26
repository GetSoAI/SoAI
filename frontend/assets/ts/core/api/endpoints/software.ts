/* SoAI - Shared API software [frontend/assets/ts/core/api/endpoints/software.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import { decodeSoftwareUpdateAcceptedResponse, decodeSoftwareUpdateCheckResponse, type SoftwareUpdateAcceptedResponse, type SoftwareUpdateCheckResponse } from '@core/api/contracts/softwareContracts.ts';

const createSoftwareEndpoints = (api: ApiClientContext): { checkUpdates: () => Promise<SoftwareUpdateCheckResponse>; updateSoAI: () => Promise<SoftwareUpdateAcceptedResponse> } => {
    return {
        checkUpdates: async (): Promise<SoftwareUpdateCheckResponse> => decodeSoftwareUpdateCheckResponse(await api.post('/api/v1/actions/software/check-for-updates')),
        updateSoAI: async (): Promise<SoftwareUpdateAcceptedResponse> => decodeSoftwareUpdateAcceptedResponse(await api.post('/api/v1/software/update-soai'))
    };
};

export { createSoftwareEndpoints };
