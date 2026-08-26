/* SoAI - Frontend MCP access token API contracts [frontend/assets/ts/core/api/contracts/mcpAccessTokenContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireJsonResponsePayload } from '@core/api/jsonResponsePayload.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { readRequiredRecordArrayField, readRequiredTrimmedStringField } from '@core/types/payloadFieldReaders.ts';
import { readPositiveFlooredIntegerOrNullValue, readRequiredPositiveTruncatedIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredBooleanValue } from '@core/types/payloadValueReaders.ts';
import { isString } from '@core/typeGuards.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

interface McpAccessTokenCreateRequest {
    label: string;
    expiresAtMs: number | null;
}

interface McpAccessTokenRecord {
    tokenId: string;
    prefix: string;
    label: string;
    createdAtMs: number;
    lastUsedAtMs: number | null;
    expiresAtMs: number | null;
    revoked: boolean;
    revokedAtMs: number | null;
}

interface McpAccessTokensListResponse {
    tokens: McpAccessTokenRecord[];
}

interface McpAccessTokenCreateResponse {
    token: string;
    metadata: McpAccessTokenRecord;
}

interface McpAccessTokenRevokeResponse {
    token: McpAccessTokenRecord;
}

const decodeMcpAccessTokenRecord = (value: JsonValue | null | undefined): McpAccessTokenRecord => {
    const record = requireRecord(value, 'MCP access token record');
    return {
        tokenId: readRequiredTrimmedStringField(record, 'token_id', 'MCP access token id'),
        prefix: readRequiredTrimmedStringField(record, 'prefix', 'MCP access token prefix'),
        label: readRequiredTrimmedStringField(record, 'label', 'MCP access token label'),
        createdAtMs: readRequiredPositiveTruncatedIntegerValue(record['created_at_ms'], 'MCP access token created_at_ms'),
        lastUsedAtMs: readPositiveFlooredIntegerOrNullValue(record['last_used_at_ms']),
        expiresAtMs: readPositiveFlooredIntegerOrNullValue(record['expires_at_ms']),
        revoked: readRequiredBooleanValue(record['revoked'], 'MCP access token revoked'),
        revokedAtMs: readPositiveFlooredIntegerOrNullValue(record['revoked_at_ms'])
    };
};

const decodeMcpAccessTokensListResponse = (value: ApiResponsePayload): McpAccessTokensListResponse => {
    const record = requireRecord(requireJsonResponsePayload(value, 'MCP access tokens list'), 'MCP access tokens list response');
    return { tokens: readRequiredRecordArrayField(record, 'tokens', 'MCP access tokens list response.tokens').map(decodeMcpAccessTokenRecord) };
};

const decodeMcpAccessTokenCreateResponse = (value: ApiResponsePayload): McpAccessTokenCreateResponse => {
    const record = requireRecord(requireJsonResponsePayload(value, 'MCP access token create'), 'MCP access token create response');
    const token = record['token'];
    if (!isString(token) || !token.trim()) throw new Error('Invalid MCP access token secret');
    return { token, metadata: decodeMcpAccessTokenRecord(record['metadata']) };
};

const decodeMcpAccessTokenRevokeResponse = (value: ApiResponsePayload): McpAccessTokenRevokeResponse => {
    const record = requireRecord(requireJsonResponsePayload(value, 'MCP access token revoke'), 'MCP access token revoke response');
    return { token: decodeMcpAccessTokenRecord(record['token']) };
};

const serializeMcpAccessTokenCreateRequest = (request: McpAccessTokenCreateRequest): JsonObject => ({ label: request.label, 'expires_at_ms': request.expiresAtMs });

export { decodeMcpAccessTokenCreateResponse, decodeMcpAccessTokenRevokeResponse, decodeMcpAccessTokensListResponse, serializeMcpAccessTokenCreateRequest };
export type { McpAccessTokenCreateRequest, McpAccessTokenCreateResponse, McpAccessTokenRecord, McpAccessTokenRevokeResponse, McpAccessTokensListResponse };
