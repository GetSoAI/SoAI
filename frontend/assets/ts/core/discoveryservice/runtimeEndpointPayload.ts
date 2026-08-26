/* SoAI - Runtime endpoint payload decoding [frontend/assets/ts/core/discoveryservice/runtimeEndpointPayload.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNumber, isObject, isString } from '@core/typeGuards.ts';
import { assertExactRecordKeys } from '@core/types/payloadRecordReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { SoaiEdition } from '@core/edition/backendEditionIntegrity.ts';
import { decodeSystemHealth } from '@core/api/contracts/systemContracts.ts';

interface RuntimeEndpointPayload {
    readonly product: 'soai';
    readonly version: string;
    readonly instanceId: string;
    readonly instanceName: string | null;
    readonly scheme: 'http' | 'https';
    readonly port: number;
    readonly preferredPort: number;
    readonly fallbackActive: boolean;
    readonly edition: SoaiEdition;
}

const readPort = (value: JsonValue | undefined, field: string): number => {
    if (!isNumber(value) || !Number.isInteger(value) || value < 1 || value > 65535) {
        throw new Error(`${field} must be an integer from 1 through 65535`);
    }
    return value;
};

const isRuntimeEndpointReachableStatus = (value: JsonValue | undefined): boolean => {
    return isString(value) && (value.toLowerCase() === 'ok' || value.toLowerCase() === 'degraded');
};

const decodeRuntimeEndpointPayload = (value: JsonValue): RuntimeEndpointPayload => {
    if (!isObject(value)) {
        throw new Error('Runtime endpoint payload must be an object');
    }
    assertExactRecordKeys(value, ['status', 'product', 'version', 'instance_id', 'instance_name', 'scheme', 'port', 'preferred_port', 'fallback_active', 'edition'], 'Runtime endpoint payload');
    const product = value['product'];
    const version = value['version'];
    const instanceId = value['instance_id'];
    const instanceName = value['instance_name'];
    const scheme = value['scheme'];
    const fallbackActive = value['fallback_active'];
    const edition = value['edition'];
    if (product !== 'soai') {
        throw new Error('Runtime endpoint payload is not a SoAI server');
    }
    if (!isString(version) || !version.trim()) {
        throw new Error('Runtime endpoint version is required');
    }
    if (!isString(instanceId) || !instanceId.trim()) {
        throw new Error('Runtime endpoint instance identity is required');
    }
    if (!isString(instanceName) && instanceName !== null) {
        throw new Error('Runtime endpoint instance name is invalid');
    }
    if (scheme !== 'http' && scheme !== 'https') {
        throw new Error('Runtime endpoint scheme is invalid');
    }
    if (typeof fallbackActive !== 'boolean') {
        throw new Error('Runtime endpoint fallback state is invalid');
    }
    if (edition !== 'soai-core' && edition !== 'soai-os') {
        throw new Error('Runtime endpoint edition is invalid');
    }
    const port = readPort(value['port'], 'port');
    const preferredPort = readPort(value['preferred_port'], 'preferred_port');
    if (fallbackActive !== (port !== preferredPort)) {
        throw new Error('Runtime endpoint fallback state is inconsistent');
    }
    const payload: RuntimeEndpointPayload = {
        product,
        version: version.trim(),
        instanceId: instanceId.trim(),
        instanceName: isString(instanceName) ? instanceName.trim() || null : null,
        scheme,
        port,
        preferredPort,
        fallbackActive,
        edition
    };
    return payload;
};

const decodeRuntimeEndpointHealthPayload = (value: JsonValue): RuntimeEndpointPayload => {
    const health = decodeSystemHealth(value);
    return {
        product: health.product,
        version: health.version,
        instanceId: health.instanceId,
        instanceName: health.instanceName,
        scheme: health.scheme,
        port: health.port,
        preferredPort: health.preferredPort,
        fallbackActive: health.fallbackActive,
        edition: health.edition
    };
};

export { decodeRuntimeEndpointHealthPayload, decodeRuntimeEndpointPayload, isRuntimeEndpointReachableStatus };
export type { RuntimeEndpointPayload };
