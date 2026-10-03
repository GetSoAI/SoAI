/* SoAI - Permission availability failure identity [frontend/assets/ts/core/access/permissionFailure.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

class WebuiPermissionsUnavailableError extends Error {
    constructor(cause: Error) {
        super('WebUI permissions are unavailable', { cause });
        this.name = 'WebuiPermissionsUnavailableError';
    }
}

export { WebuiPermissionsUnavailableError };
