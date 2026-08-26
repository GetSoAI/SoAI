/* SoAI - Frontend WebUI message mutation boundary contracts [frontend/assets/ts/core/api/contracts/webuiMessageMutationContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

interface MessageResubmitRequest {
    expectedLastModifiedAtMs: number;
    createdAtMs: number;
    messageId: number;
    message: JsonValue;
}

interface MessageTargetMutationRequest {
    expectedLastModifiedAtMs: number;
    createdAtMs: number;
    messageId: number;
}

const serializeMessageWriteRequest = (messages: JsonValue, expectedLastModifiedAtMs: number): JsonObject => ({
    messages,
    'expected_last_modified_at_ms': expectedLastModifiedAtMs
});

const serializeMessageTargetMutationRequest = (request: MessageTargetMutationRequest): JsonObject => ({
    'expected_last_modified_at_ms': request.expectedLastModifiedAtMs,
    'created_at_ms': request.createdAtMs,
    'message_id': request.messageId
});

const serializeMessageResubmitRequest = (request: MessageResubmitRequest): JsonObject => ({
    ...serializeMessageTargetMutationRequest(request),
    message: request.message
});

export { serializeMessageResubmitRequest, serializeMessageTargetMutationRequest, serializeMessageWriteRequest };
export type { MessageResubmitRequest, MessageTargetMutationRequest };
