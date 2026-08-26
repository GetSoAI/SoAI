/* SoAI - Shared API configuration endpoints [frontend/assets/ts/core/api/endpoints/configs.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import type { OpaqueJsonObject, OpaqueJsonValue } from '@core/api/contracts/opaquePayload.ts';
import { buildSignalRequestOptions, type SignalOptions } from '@core/api/requestOptions.ts';
import { decodeConfigListResponse, decodeConfigResponse, decodeConfigUpdateResponse, type ConfigUpdateResponse } from '@core/api/contracts/configContracts.ts';

const createConfigsEndpoints = (api: ApiClientContext): { list: () => Promise<string[]>; get: (name: string, options?: SignalOptions) => Promise<OpaqueJsonObject>; update: (name: string, changes: OpaqueJsonValue) => Promise<ConfigUpdateResponse> } => {
    return {
        list: async (): Promise<string[]> => decodeConfigListResponse(await api.get('/api/v1/configs')),
        get: async (name: string, options: SignalOptions = {}): Promise<OpaqueJsonObject> => decodeConfigResponse(await api.get(`/api/v1/configs/${api.encodePathSegment(name)}`, buildSignalRequestOptions(options))),
        update: async (name: string, changes: OpaqueJsonValue): Promise<ConfigUpdateResponse> => decodeConfigUpdateResponse(await api.patch(`/api/v1/configs/${api.encodePathSegment(name)}`, { changes }))
    };
};

export { createConfigsEndpoints };
