/* SoAI - Frontend WebUI session contracts [frontend/assets/ts/core/api/contracts/webuiSessionContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { isBoolean, isNonEmptyString, isPositiveInteger, isString } from '@core/typeGuards.ts';
import { isJsonObject } from '@core/types/jsonValues.ts';

const CANONICAL_UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

interface WebuiSession {
    jti: string;
    deviceId: string | null;
    deviceLabel: string;
    clientType: 'web' | 'android';
    userAgent: string;
    createdAtMs: number;
    lastSeenAtMs: number;
    expiresAtMs: number;
    current: boolean;
}

const decodeWebuiSession = (value: ApiResponsePayload): WebuiSession => {
    if (!isJsonObject(value)) throw new Error('WebUI session must be an object');
    const jti = value['jti'];
    const deviceId = value['device_id'];
    const deviceLabel = value['device_label'];
    const clientType = value['client_type'];
    const userAgent = value['user_agent'];
    const createdAt = value['created_at_ms'];
    const lastSeenAt = value['last_seen_at_ms'];
    const expiresAt = value['expires_at_ms'];
    const current = value['current'];
    const clientIdentityValid = (clientType === 'web' && deviceId === null) || (clientType === 'android' && isNonEmptyString(deviceId) && CANONICAL_UUID_PATTERN.test(deviceId));
    const timestampsValid = isPositiveInteger(createdAt) && isPositiveInteger(lastSeenAt) && isPositiveInteger(expiresAt) && lastSeenAt >= createdAt && expiresAt > createdAt;
    const textLengthsValid = isNonEmptyString(deviceLabel) && Array.from(deviceLabel).length <= 80 && isString(userAgent) && Array.from(userAgent).length <= 512;
    if (!isNonEmptyString(jti) || jti.length > 128 || !textLengthsValid || !clientIdentityValid || !timestampsValid || !isBoolean(current)) throw new Error('WebUI session contains invalid fields');
    return { jti, deviceId, deviceLabel, clientType, userAgent, createdAtMs: createdAt, lastSeenAtMs: lastSeenAt, expiresAtMs: expiresAt, current };
};

const decodeWebuiSessions = (value: ApiResponsePayload): WebuiSession[] => {
    if (!isJsonObject(value) || !Array.isArray(value['sessions'])) throw new Error('WebUI sessions response must contain an array');
    return value['sessions'].map(decodeWebuiSession);
};

export { decodeWebuiSessions };
export type { WebuiSession };
