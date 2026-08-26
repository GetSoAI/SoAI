/* SoAI - Exact V1 plugin mutation transport serializers [frontend/assets/ts/core/plugins/pluginMutationContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireMutationRequestId } from '@core/mutations/mutationIdentity.ts';
import { requirePortablePluginIdentifier } from '@core/plugins/portablePluginIdentifier.ts';
import { cloneJsonObject } from '@core/primitives/clone.ts';
import { isJsonValue, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

type BackendWebSocketCommandType = 'plugin_backend_install' | 'plugin_backend_update' | 'plugin_backend_remove';
type BackendRestCommandType = 'install' | 'update' | 'remove';
type ProviderMutationType = 'create' | 'update' | 'delete';

const PROVIDER_MUTATION_FIELDS = new Set(['api_key', 'api_url', 'context_window_tokens', 'extra_headers', 'extra_query_params', 'models_filter', 'name']);

interface BackendWebSocketCommandInput {
    commandType: BackendWebSocketCommandType;
    pluginName: string;
    backendVariantId?: string;
    deleteModels?: boolean;
}

interface BackendWebSocketCommand {
    type: BackendWebSocketCommandType;
    body: JsonObject;
}

interface BackendRestRequestInput {
    commandType: BackendRestCommandType;
    pluginName: string;
    taskId: string;
    backendVariantId?: string;
    deleteModels?: boolean;
}

interface BackendRestRequest {
    pathPluginName: string;
    query: { 'task_id': string };
    body: JsonObject;
}

interface ClonePluginRequestInput {
    cloneModels: boolean;
    taskId: string;
    targetName?: string | null;
    fieldOverrides?: Readonly<Record<string, JsonValue>> | null;
}

interface ProviderMutationInput {
    operation: ProviderMutationType;
    operationId: string;
    revision?: number;
    body: JsonObject;
}

interface SerializedProviderMutation {
    headers: Record<string, string>;
    body: JsonObject;
}

const requireNonEmpty = (value: string, label: string): string => {
    const normalized = value.trim();
    if (!normalized) throw new Error(`${label} is required`);
    return normalized;
};

const serializeProviderSnapshotRequest = (pluginName: string): JsonObject => ({ 'plugin_name': requirePortablePluginIdentifier(pluginName, 'Provider snapshot plugin name') });

const serializeBackendWebSocketCommand = (input: BackendWebSocketCommandInput): BackendWebSocketCommand => {
    const body: JsonObject = { 'plugin_name': requirePortablePluginIdentifier(input.pluginName, 'Backend operation plugin name') };
    if (input.commandType === 'plugin_backend_remove') {
        if (typeof input.deleteModels !== 'boolean') throw new Error('Backend remove requires deleteModels');
        body['delete_models'] = input.deleteModels;
    } else if (input.backendVariantId !== undefined) {
        body['backend_variant_id'] = requireNonEmpty(input.backendVariantId, 'Backend variant identifier');
    }
    return { type: input.commandType, body };
};

const serializeBackendRestRequest = (input: BackendRestRequestInput): BackendRestRequest => {
    const body: JsonObject = {};
    if (input.commandType === 'remove') {
        if (typeof input.deleteModels !== 'boolean') throw new Error('Backend remove requires deleteModels');
        body['delete_models'] = input.deleteModels;
    } else if (input.backendVariantId !== undefined) {
        body['backend_variant_id'] = requireNonEmpty(input.backendVariantId, 'Backend variant identifier');
    }
    return {
        pathPluginName: requirePortablePluginIdentifier(input.pluginName, 'Backend operation plugin name'),
        query: { 'task_id': requireMutationRequestId(input.taskId) },
        body
    };
};

const serializeClonePluginRequest = (input: ClonePluginRequestInput): JsonObject => {
    if (typeof input.cloneModels !== 'boolean') throw new Error('Clone request requires cloneModels');
    const body: JsonObject = {
        'clone_models': input.cloneModels,
        'task_id': requireMutationRequestId(input.taskId)
    };
    if (input.targetName !== undefined && input.targetName !== null) body['target_name'] = requirePortablePluginIdentifier(input.targetName, 'Clone target name');
    if (input.fieldOverrides !== undefined && input.fieldOverrides !== null) {
        const overrides: JsonObject = {};
        for (const [fieldName, fieldValue] of Object.entries(input.fieldOverrides)) {
            if (!fieldName.trim() || !isJsonValue(fieldValue)) throw new Error('Clone field overrides must contain JSON values under non-empty field names');
            overrides[fieldName] = fieldValue;
        }
        body['field_overrides'] = overrides;
    }
    return body;
};

const serializeProviderMutation = (input: ProviderMutationInput): SerializedProviderMutation => {
    const headers: Record<string, string> = { 'Idempotency-Key': requireMutationRequestId(input.operationId) };
    if (input.operation !== 'create') {
        if (!Number.isSafeInteger(input.revision) || input.revision === undefined || input.revision < 0) throw new Error('Provider update and delete require a non-negative revision');
        headers['If-Match'] = `"${String(input.revision)}"`;
    }
    const body = cloneJsonObject(input.body);
    const fields = Object.keys(body);
    if (input.operation === 'delete') {
        if (fields.length > 0) throw new Error('Provider delete body must be empty');
        return { headers, body };
    }
    if (fields.some((fieldName) => !PROVIDER_MUTATION_FIELDS.has(fieldName))) throw new Error('Provider mutation body contains unsupported fields');
    if (input.operation === 'create' && typeof body['api_url'] !== 'string') throw new Error('Provider create requires api_url');
    if (input.operation === 'update' && fields.length === 0) throw new Error('Provider update requires at least one field');
    for (const fieldName of fields) {
        const value = body[fieldName];
        const nullableCreateName = input.operation === 'create' && fieldName === 'name' && value === null;
        if ((fieldName === 'api_url' || fieldName === 'name') && !nullableCreateName && (typeof value !== 'string' || !value.trim())) throw new Error(`Provider ${fieldName} must be a non-empty string`);
        if (fieldName === 'api_key' && value !== null && typeof value !== 'string') throw new Error('Provider api_key must be a string or null');
        if (fieldName === 'models_filter' && value !== null && (!Array.isArray(value) || value.some((entry) => typeof entry !== 'string'))) throw new Error('Provider models_filter must be an array of strings or null');
        if (fieldName === 'context_window_tokens' && value !== null && (!Number.isSafeInteger(value) || typeof value !== 'number' || value < 1)) throw new Error('Provider context_window_tokens must be a positive integer or null');
        if ((fieldName === 'extra_headers' || fieldName === 'extra_query_params') && value !== null && (typeof value !== 'object' || Array.isArray(value) || Object.values(value).some((entry) => typeof entry !== 'string'))) throw new Error(`Provider ${fieldName} must be an object of string values or null`);
    }
    return { headers, body };
};

export { serializeBackendRestRequest, serializeBackendWebSocketCommand, serializeClonePluginRequest, serializeProviderMutation, serializeProviderSnapshotRequest };
export type { BackendRestCommandType, BackendRestRequest, BackendWebSocketCommand, BackendWebSocketCommandType, ClonePluginRequestInput, ProviderMutationType, SerializedProviderMutation };
