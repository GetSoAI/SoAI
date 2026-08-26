/* SoAI - Shared API validation [frontend/assets/ts/core/api/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getDiscoveryService } from '@core/discoveryservice/public.ts';
import type { AuthManagerContract, DiscoveryServiceRef } from '@core/api/types/apiClient.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

type AuthManagerCandidate = Partial<AuthManagerContract> | null | undefined | void;

const readStringRecord = (value: JsonObject | null | undefined | void, label: string): Record<string, string> => {
    if (value === null || value === undefined) {
        throw new Error(`${label} must be an object`);
    }
    const result: Record<string, string> = {};
    for (const [key, entry] of Object.entries(value)) {
        if (typeof entry !== 'string') {
            throw new Error(`${label}.${key} must be a string`);
        }
        result[key] = entry;
    }
    return result;
};

const isAuthManagerContract = (value: AuthManagerCandidate): value is AuthManagerContract => {
    if (value === null || value === undefined) {
        return false;
    }
    const isAuthenticated = value.isAuthenticated;
    if (typeof isAuthenticated !== 'boolean') {
        return false;
    }
    const logout = value['logout'];
    if (logout !== null && logout !== undefined && typeof logout !== 'function') {
        return false;
    }
    return true;
};

const resolveDiscoveryService = async (): Promise<DiscoveryServiceRef> => {
    const service = getDiscoveryService();
    if (typeof service.discoverEndpoint !== 'function') {
        throw new Error('Discovery service is not available');
    }
    return service;
};

export { isAuthManagerContract, readStringRecord, resolveDiscoveryService };
