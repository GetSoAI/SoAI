/* SoAI - Frontend manual install path API contracts [frontend/assets/ts/core/api/contracts/manualInstallPathContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { isJsonObject } from '@core/types/jsonValues.ts';

interface ManualInstallPathResponse {
    resourceType: string;
    configuredPath: string;
    resolvedPath: string;
}

const decodeManualInstallPathResponse = (value: ApiResponsePayload, expectedResourceType: string): ManualInstallPathResponse => {
    if (!isJsonObject(value)) throw new TypeError('Manual install path response must be an object');
    const resourceType = toTrimmedString(value['resource_type']);
    const configuredPath = toTrimmedString(value['configured_path']);
    const resolvedPath = toTrimmedString(value['resolved_path']);
    if (resourceType !== expectedResourceType) throw new TypeError(`Manual install path response resource_type must be ${expectedResourceType}`);
    if (!configuredPath) throw new TypeError('Manual install path response configured_path is required');
    if (!resolvedPath) throw new TypeError('Manual install path response resolved_path is required');
    return { resourceType, configuredPath, resolvedPath };
};

export { decodeManualInstallPathResponse };
export type { ManualInstallPathResponse };
