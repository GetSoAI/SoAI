/* SoAI - Frontend WebUI SoAI link and path request serialization [frontend/assets/ts/core/api/contracts/webuiSoaiPathSerialization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SoaiLinkResolveRequest, SoaiPathBrowseRequest, SoaiPathContentPart, SoaiPathOperationRequest } from '@core/api/contracts/webuiChatOperationContractTypes.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

const serializeSoaiPathContentPart = (contentPart: SoaiPathContentPart): JsonObject => ({
    type: contentPart.type,
    'entry_type': contentPart.entryType,
    'source_reference': { type: contentPart.sourceReference.type, value: contentPart.sourceReference.value },
    'tool_reference': { type: contentPart.toolReference.type, value: contentPart.toolReference.value },
    'workspace_scope': { type: contentPart.workspaceScope.type, 'root_fingerprint': contentPart.workspaceScope.rootFingerprint },
    'target_fingerprint': { type: contentPart.targetFingerprint.type, value: contentPart.targetFingerprint.value },
    title: contentPart.title,
    'preview_type': contentPart.previewType,
    'mime_type': contentPart.mimeType,
    'size_bytes': contentPart.sizeBytes,
    'modified_at_ms': contentPart.modifiedAtMs,
    'resolved_at_ms': contentPart.resolvedAtMs
});

const serializeSoaiPathOperationRequest = (request: SoaiPathOperationRequest): JsonObject => {
    const serialized: JsonObject = {};
    if (request.contentPart !== undefined) serialized['content_part'] = serializeSoaiPathContentPart(request.contentPart);
    if (request.sourceReference !== undefined) serialized['source_reference'] = { type: request.sourceReference.type, value: request.sourceReference.value };
    if (request.workspaceScope !== undefined) serialized['workspace_scope'] = { type: request.workspaceScope.type, 'root_fingerprint': request.workspaceScope.rootFingerprint };
    return serialized;
};

const serializeSoaiLinkResolveRequest = (request: SoaiLinkResolveRequest): JsonObject => ({ 'raw_text': request.rawText });

const serializeSoaiPathBrowseRequest = (request: SoaiPathBrowseRequest): JsonObject => ({ query: request.query, limit: request.limit });

export { serializeSoaiLinkResolveRequest, serializeSoaiPathBrowseRequest, serializeSoaiPathContentPart, serializeSoaiPathOperationRequest };
