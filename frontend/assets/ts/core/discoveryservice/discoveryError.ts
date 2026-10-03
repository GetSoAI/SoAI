/* SoAI - Backend discovery failure identity [frontend/assets/ts/core/discoveryservice/discoveryError.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

class BackendDiscoveryError extends Error {
    constructor(cause: Error) {
        super('Backend discovery failed', { cause });
        this.name = 'BackendDiscoveryError';
    }
}

export { BackendDiscoveryError };
