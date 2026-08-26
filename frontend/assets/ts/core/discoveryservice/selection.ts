/* SoAI - Deterministic discovered endpoint selection [frontend/assets/ts/core/discoveryservice/selection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RuntimeEndpointPayload } from '@core/discoveryservice/runtimeEndpointPayload.ts';

interface DiscoveredEndpoint extends RuntimeEndpointPayload {
    readonly baseUrl: string;
}

type DiscoverySelection = { readonly type: 'selected'; readonly endpoint: DiscoveredEndpoint } | { readonly type: 'ambiguous'; readonly endpoints: readonly DiscoveredEndpoint[] } | { readonly type: 'notFound' };

const selectDiscoveredEndpoint = (candidates: readonly DiscoveredEndpoint[], targetInstanceId: string | null): DiscoverySelection => {
    const uniqueByEndpoint = new Map<string, DiscoveredEndpoint>();
    for (const candidate of candidates) {
        const key = `${candidate.instanceId}\n${candidate.scheme}\n${candidate.baseUrl}`;
        if (!uniqueByEndpoint.has(key)) {
            uniqueByEndpoint.set(key, candidate);
        }
    }
    const uniqueCandidates = Array.from(uniqueByEndpoint.values());
    const matching = targetInstanceId ? uniqueCandidates.filter((candidate) => candidate.instanceId === targetInstanceId) : uniqueCandidates;
    if (matching.length === 0) {
        return { type: 'notFound' };
    }
    if (matching.length === 1) {
        const endpoint = matching[0];
        if (!endpoint) {
            return { type: 'notFound' };
        }
        return { type: 'selected', endpoint };
    }
    return { type: 'ambiguous', endpoints: matching };
};

export { selectDiscoveredEndpoint };
export type { DiscoveredEndpoint, DiscoverySelection };
