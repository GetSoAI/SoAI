/* SoAI - Shared API routing [frontend/assets/ts/core/api/endpoints/routing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import { decodeRoutingConfigSnapshot, type RoutingConfigSnapshot } from '@core/api/contracts/routingConfigContracts.ts';
import { decodeRoutingMutationResponse, decodeVirtualModelListResponse, decodeVirtualModelResponse, serializeVirtualModelCreateRequest, serializeVirtualModelUpdateRequest, type VirtualModelCreateRequest, type VirtualModelResponse, type VirtualModelUpdateRequest } from '@core/api/contracts/virtualModelContracts.ts';
import type { SuccessfulMutationResponse } from '@core/api/contracts/successfulMutationContract.ts';

const createRoutingEndpoints = (api: ApiClientContext): { config: () => Promise<RoutingConfigSnapshot>; virtualModels: { list: () => Promise<VirtualModelResponse[]>; get: (name: string) => Promise<VirtualModelResponse>; create: (payload: VirtualModelCreateRequest) => Promise<SuccessfulMutationResponse>; update: (name: string, payload: VirtualModelUpdateRequest) => Promise<SuccessfulMutationResponse>; setEnabled: (name: string, payload: { enabled: boolean }) => Promise<SuccessfulMutationResponse>; delete: (name: string) => Promise<SuccessfulMutationResponse> } } => {
    return {
        config: async (): Promise<RoutingConfigSnapshot> => decodeRoutingConfigSnapshot(await api.get('/api/v1/routing/config')),
        virtualModels: {
            list: async (): Promise<VirtualModelResponse[]> => decodeVirtualModelListResponse(await api.get('/api/v1/routing/virtual-models')),
            get: async (name: string): Promise<VirtualModelResponse> => decodeVirtualModelResponse(await api.get(`/api/v1/routing/virtual-models/${api.encodePathSegment(name)}`)),
            create: async (payload: VirtualModelCreateRequest): Promise<SuccessfulMutationResponse> => {
                return decodeRoutingMutationResponse(await api.post('/api/v1/routing/virtual-models', serializeVirtualModelCreateRequest(payload)));
            },
            update: async (name: string, payload: VirtualModelUpdateRequest): Promise<SuccessfulMutationResponse> => {
                return decodeRoutingMutationResponse(await api.patch(`/api/v1/routing/virtual-models/${api.encodePathSegment(name)}`, serializeVirtualModelUpdateRequest(payload)));
            },
            setEnabled: async (name: string, payload: { enabled: boolean }): Promise<SuccessfulMutationResponse> => decodeRoutingMutationResponse(await api.patch(`/api/v1/routing/virtual-models/${api.encodePathSegment(name)}/enabled`, payload)),
            delete: async (name: string): Promise<SuccessfulMutationResponse> => decodeRoutingMutationResponse(await api.delete(`/api/v1/routing/virtual-models/${api.encodePathSegment(name)}`))
        }
    };
};

export { createRoutingEndpoints };
