/* SoAI - Frontend WebUI chat operation response contracts [frontend/assets/ts/core/api/contracts/webuiChatOperationContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { decodeRawResponse } from '@core/api/contracts/systemContracts.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredBooleanValue, readRequiredEnumValue, readRequiredEpochMsValue, readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import { readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { isJsonArray, isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type {
    AskUserAnswerRequest,
    AskUserInteractionResolutionRequest,
    ComparisonTurnPreflightRequest,
    ComparisonTurnPreflightResponse,
    ComparisonTurnPreflightVariantResponse,
    ConversationAttentionRenderedRequest,
    ConversationInteractionEntry,
    ConversationInteractionFocusResponse,
    ConversationInteractionResolutionResponse,
    ConversationJsonExportRequest,
    ConversationMcpConfigResponse,
    ConversationMcpConfigUpdateRequest,
    ConversationMcpKnowledgeStateResponse,
    ConversationMcpToolCatalogResponse,
    ConversationMcpToolEntry,
    ConversationPendingInteractionResponse,
    ConversationPendingInteractionsResponse,
    ConversationPdfExportAcceptedResponse,
    ConversationPdfExportStartRequest,
    ConversationSearchConfigResponse,
    ConversationSearchConfigUpdateRequest,
    ConversationStreamStatusResponse,
    ConversationWorkspacePathConfigResponse,
    ConversationWorkspacePathConfigUpdateRequest,
    SecretPromptInteractionResolutionRequest,
    SoaiLinkResolveRecord,
    SoaiLinkResolveRequest,
    SoaiLinkResolveResponse,
    SoaiPathContentPart,
    SoaiPathOpenResponse,
    SoaiPathOperationRequest,
    SoaiPathPreviewEntry,
    SoaiPathPreviewResponse,
    SoaiPathReadResponse,
    SoaiPathTokenResponse,
    ToolApprovalInteractionResolutionRequest
} from '@core/api/contracts/webuiChatOperationContractTypes.ts';
const MCP_BLOCKING_REASONS: readonly ['disabled', 'empty', 'model_without_tool_calling', 'missing_required_tools'] = ['disabled', 'empty', 'model_without_tool_calling', 'missing_required_tools'];

const requireString = (value: JsonValue | undefined, label: string): string => readRequiredTrimmedStringValue(value, label);
const requireNullableString = (value: JsonValue | undefined, label: string): string | null => (value === null || value === undefined ? null : readRequiredTrimmedStringValue(value, label));
const requireJsonArray = (value: JsonValue | undefined, label: string): JsonValue[] => {
    if (!isJsonArray(value)) throw new TypeError(`${label} must be an array.`);
    return [...value];
};

const decodeInteractionEntry = (value: JsonValue, label: string): ConversationInteractionEntry => {
    const record = requireRecord(value, label);
    return { taskId: requireString(record['task_id'], `${label}.task_id`), interactionType: requireString(record['interaction_type'], `${label}.interaction_type`), notificationId: requireNullableString(record['notification_id'], `${label}.notification_id`), createdAtMs: readRequiredEpochMsValue(record['created_at_ms'], `${label}.created_at_ms`), payload: record['payload'] === undefined ? null : record['payload'] };
};
const decodeInteractionResolution = (value: ApiResponsePayload): ConversationInteractionResolutionResponse => {
    const record = requireRecord(value, 'Conversation interaction resolution response');
    return { taskId: requireString(record['task_id'], 'Conversation interaction resolution response.task_id'), status: requireString(record['status'], 'Conversation interaction resolution response.status') };
};
const decodeInteractionFocus = (value: ApiResponsePayload): ConversationInteractionFocusResponse => {
    const record = requireRecord(value, 'Conversation interaction focus response');
    return {
        taskId: requireString(record['task_id'], 'Conversation interaction focus response.task_id'),
        interactionType: readRequiredEnumValue(record['interaction_type'], 'Conversation interaction focus response.interaction_type', ['ask_user', 'tool_approval', 'vault_secret_request'])
    };
};
const decodePendingInteractions = (value: ApiResponsePayload): ConversationPendingInteractionsResponse => {
    const record = requireRecord(value, 'Conversation pending interactions response');
    return { convId: requireString(record['conv_id'], 'Conversation pending interactions response.conv_id'), interactions: requireJsonArray(record['interactions'], 'Conversation pending interactions response.interactions').map((entry, index) => decodeInteractionEntry(entry, `Conversation pending interactions response.interactions[${String(index)}]`)) };
};
const decodePendingInteraction = (value: ApiResponsePayload): ConversationPendingInteractionResponse => {
    const record = requireRecord(value, 'Conversation pending interaction response');
    const interaction = record['interaction'];
    return { convId: requireString(record['conv_id'], 'Conversation pending interaction response.conv_id'), interaction: interaction === null ? null : interaction === undefined ? null : decodeInteractionEntry(interaction, 'Conversation pending interaction response.interaction') };
};
const decodeStreamStatus = (value: ApiResponsePayload): ConversationStreamStatusResponse => {
    const record = requireRecord(value, 'Conversation stream status response');
    const status = readRequiredEnumValue(record['start_admission'], 'Conversation stream status response.start_admission', ['inactive', 'busy', 'unknown']);
    const lifecycle = readRequiredEnumValue(record['stream_lifecycle'], 'Conversation stream status response.stream_lifecycle', ['inactive', 'streaming', 'terminalizing']);
    const result: ConversationStreamStatusResponse = { active: readRequiredBooleanValue(record['active'], 'Conversation stream status response.active'), conversationId: requireString(record['conversation_id'], 'Conversation stream status response.conversation_id'), startAdmission: status, streamLifecycle: lifecycle, canAcceptConversationInput: readRequiredBooleanValue(record['can_accept_conversation_input'], 'Conversation stream status response.can_accept_conversation_input'), canStartNextPrompt: readRequiredBooleanValue(record['can_start_next_prompt'], 'Conversation stream status response.can_start_next_prompt'), canAcceptSteerPrompt: readRequiredBooleanValue(record['can_accept_steer_prompt'], 'Conversation stream status response.can_accept_steer_prompt'), activeToolCallCount: readRequiredNonNegativeIntegerValue(record['active_tool_call_count'], 'Conversation stream status response.active_tool_call_count') };
    if (typeof record['request_id'] === 'string') result.requestId = record['request_id'];
    if (typeof record['assistant_at_ms'] === 'number') result.assistantAtMs = record['assistant_at_ms'];
    if (typeof record['assistant_turn_at_ms'] === 'number') result.assistantTurnAtMs = record['assistant_turn_at_ms'];
    if (typeof record['model_variant_index'] === 'number') result.modelVariantIndex = record['model_variant_index'];
    if (typeof record['model_id'] === 'string') result.modelId = record['model_id'];
    if (typeof record['preview_key'] === 'string') result.previewKey = record['preview_key'];
    if (isJsonObject(record['preview_args'])) result.previewArguments = record['preview_args'];
    if (typeof record['preview_generated_at_ms'] === 'number') result.previewGeneratedAtMs = record['preview_generated_at_ms'];
    if (typeof record['preview_cooldown_ms'] === 'number') result.previewCooldownMs = record['preview_cooldown_ms'];
    if (typeof record['preview_trigger'] === 'string') result.previewTrigger = record['preview_trigger'];
    return result;
};
const decodeSoaiPathContentPart = (value: JsonValue | undefined, label: string): SoaiPathContentPart => {
    const record = requireRecord(value, label);
    const source = requireRecord(record['source_reference'], `${label}.source_reference`);
    const tool = requireRecord(record['tool_reference'], `${label}.tool_reference`);
    const scope = requireRecord(record['workspace_scope'], `${label}.workspace_scope`);
    const fingerprint = requireRecord(record['target_fingerprint'], `${label}.target_fingerprint`);
    return {
        type: 'soai_path',
        entryType: readRequiredEnumValue(record['entry_type'], `${label}.entry_type`, ['file', 'folder']),
        sourceReference: { type: 'conversation_virtual_path', value: requireString(source['value'], `${label}.source_reference.value`) },
        toolReference: { type: 'workspace_relative_path', value: requireString(tool['value'], `${label}.tool_reference.value`) },
        workspaceScope: { type: 'conversation_effective_workspace', rootFingerprint: requireString(scope['root_fingerprint'], `${label}.workspace_scope.root_fingerprint`) },
        targetFingerprint: { type: readRequiredEnumValue(fingerprint['type'], `${label}.target_fingerprint.type`, ['file_sha256', 'folder_listing_sha256']), value: requireString(fingerprint['value'], `${label}.target_fingerprint.value`) },
        title: requireString(record['title'], `${label}.title`),
        previewType: requireString(record['preview_type'], `${label}.preview_type`),
        mimeType: requireNullableString(record['mime_type'], `${label}.mime_type`),
        sizeBytes: record['size_bytes'] === null || record['size_bytes'] === undefined ? null : readRequiredNonNegativeIntegerValue(record['size_bytes'], `${label}.size_bytes`),
        modifiedAtMs: readRequiredEpochMsValue(record['modified_at_ms'], `${label}.modified_at_ms`),
        resolvedAtMs: readRequiredEpochMsValue(record['resolved_at_ms'], `${label}.resolved_at_ms`)
    };
};
const decodeSoaiAvailable = (value: JsonValue, label: string): SoaiPathContentPart => {
    const record = requireRecord(value, label);
    return decodeSoaiPathContentPart(record['content_part'], `${label}.content_part`);
};
const decodeSoaiPreview = (value: ApiResponsePayload): SoaiPathPreviewResponse => {
    const record = requireRecord(value, 'SoAI path preview response');
    if (record['state'] === 'unavailable') return { state: 'unavailable' };
    const contentPart = decodeSoaiAvailable(record, 'SoAI path preview response');
    const entries = record['entries'];
    if (entries === undefined) return { state: 'available', contentPart: contentPart };
    if (!isJsonArray(entries)) throw new TypeError('SoAI path preview response.entries must be an array.');
    return {
        state: 'available',
        contentPart: contentPart,
        entries: entries.map((entry, index) => {
            const item = requireRecord(entry, `SoAI path preview response.entries[${String(index)}]`);
            return { name: requireString(item['name'], `SoAI path preview response.entries[${String(index)}].name`), entryType: readRequiredEnumValue(item['entry_type'], 'SoAI path preview entry_type', ['file', 'folder']), sizeBytes: readRequiredNonNegativeIntegerValue(item['size_bytes'], 'SoAI path preview size_bytes'), modifiedAtMs: readRequiredEpochMsValue(item['modified_at_ms'], 'SoAI path preview modified_at_ms') };
        })
    };
};
const decodeSoaiRead = (value: ApiResponsePayload): SoaiPathReadResponse => {
    const record = requireRecord(value, 'SoAI path read response');
    if (record['state'] === 'unavailable') return { state: 'unavailable' };
    return {
        state: 'available',
        contentPart: decodeSoaiAvailable(record, 'SoAI path read response'),
        text:
            typeof record['text'] === 'string'
                ? record['text']
                : (() => {
                      throw new TypeError('SoAI path read response.text must be a string.');
                  })()
    };
};
const decodeSoaiOpen = (value: ApiResponsePayload): SoaiPathOpenResponse => {
    const record = requireRecord(value, 'SoAI path open response');
    if (record['state'] === 'unavailable') return { state: 'unavailable' };
    return { state: 'available', virtualPath: requireString(record['virtual_path'], 'SoAI path open response.virtual_path') };
};
const decodeSoaiToken = (value: ApiResponsePayload): SoaiPathTokenResponse => {
    const record = requireRecord(value, 'SoAI path token response');
    if (record['state'] === 'unavailable') return { state: 'unavailable' };
    return { state: 'available', token: requireString(record['token'], 'SoAI path token response.token') };
};
const decodeComparisonTurnPreflight = (value: ApiResponsePayload): ComparisonTurnPreflightResponse => {
    const record = requireRecord(value, 'Comparison turn preflight response');
    const variants = requireJsonArray(record['variants'], 'Comparison turn preflight response.variants').map((entry, index) => {
        const variant = requireRecord(entry, `Comparison turn preflight response.variants[${String(index)}]`);
        return { modelVariantIndex: readRequiredNonNegativeIntegerValue(variant['model_variant_index'], `Comparison turn preflight response.variants[${String(index)}].model_variant_index`), requestedModelId: requireString(variant['requested_model_id'], `Comparison turn preflight response.variants[${String(index)}].requested_model_id`), resolvedModelId: requireString(variant['resolved_model_id'], `Comparison turn preflight response.variants[${String(index)}].resolved_model_id`), assistantAtMs: readRequiredEpochMsValue(variant['assistant_at_ms'], `Comparison turn preflight response.variants[${String(index)}].assistant_at_ms`) };
    });
    return { assistantTurnAtMs: readRequiredEpochMsValue(record['assistant_turn_at_ms'], 'Comparison turn preflight response.assistant_turn_at_ms'), variants };
};
const decodeSoaiLinkResolve = (value: ApiResponsePayload): SoaiLinkResolveResponse => {
    const record = requireRecord(value, 'SoAI link resolve response');
    const records = requireJsonArray(record['records'], 'SoAI link resolve response.records').map((entry, index) => {
        const item = requireRecord(entry, `SoAI link resolve response.records[${String(index)}]`);
        return { token: requireString(item['token'], 'SoAI link resolve response.records[].token'), occurrenceIndex: readRequiredNonNegativeIntegerValue(item['occurrence_index'], 'SoAI link resolve response.records[].occurrence_index'), displayLabel: requireNullableString(item['display_label'], 'SoAI link resolve response.records[].display_label'), contentPart: decodeSoaiPathContentPart(item['content_part'], 'SoAI link resolve response.records[].content_part') };
    });
    return { records, tokenCount: readRequiredNonNegativeIntegerValue(record['token_count'], 'SoAI link resolve response.token_count') };
};
const decodeWorkspacePathConfig = (value: ApiResponsePayload): ConversationWorkspacePathConfigResponse => {
    const record = requireRecord(value, 'Conversation workspace path response');
    return { convId: requireString(record['conv_id'], 'Conversation workspace path response.conv_id'), workspacePath: requireNullableString(record['workspace_path'], 'Conversation workspace path response.workspace_path'), effectiveWorkspacePath: requireNullableString(record['effective_workspace_path'], 'Conversation workspace path response.effective_workspace_path'), effectiveRootFingerprint: requireNullableString(record['effective_root_fingerprint'], 'Conversation workspace path response.effective_root_fingerprint'), isValid: readRequiredBooleanValue(record['is_valid'], 'Conversation workspace path response.is_valid'), validationCode: requireNullableString(record['validation_code'], 'Conversation workspace path response.validation_code'), validationMessage: requireNullableString(record['validation_message'], 'Conversation workspace path response.validation_message') };
};
const decodeSearchConfig = (value: ApiResponsePayload): ConversationSearchConfigResponse => {
    const record = requireRecord(value, 'Conversation search config response');
    const providers = requireJsonArray(record['available_providers'], 'Conversation search config response.available_providers');
    return { enabled: readRequiredBooleanValue(record['enabled'], 'Conversation search config response.enabled'), defaultProvider: requireNullableString(record['default_provider'], 'Conversation search config response.default_provider'), maxResults: readRequiredNonNegativeIntegerValue(record['max_results'], 'Conversation search config response.max_results'), availableProviders: providers.map((entry, index) => requireString(entry, `Conversation search config response.available_providers[${String(index)}]`)) };
};
const decodeStringList = (value: JsonValue | undefined, label: string): string[] => requireJsonArray(value, label).map((entry, index) => requireString(entry, `${label}[${String(index)}]`));
const decodeMcpConfig = (value: ApiResponsePayload): ConversationMcpConfigResponse => {
    const record = requireRecord(value, 'Conversation MCP config response');
    const knowledge = requireRecord(record['knowledge_state'], 'Conversation MCP config response.knowledge_state');
    const blocking = knowledge['blocking_reason'];
    return {
        convId: requireString(record['conv_id'], 'Conversation MCP config response.conv_id'),
        defaultTools: decodeStringList(record['default_tools'], 'Conversation MCP config response.default_tools'),
        planTools: decodeStringList(record['plan_tools'], 'Conversation MCP config response.plan_tools'),
        executeTools: decodeStringList(record['execute_tools'], 'Conversation MCP config response.execute_tools'),
        serverConfigs: Object.fromEntries(Object.entries(requireRecord(record['server_configs'], 'Conversation MCP config response.server_configs')).map(([key, entry]) => [key, readRequiredBooleanValue(entry, `Conversation MCP config response.server_configs.${key}`)])),
        toolsEnabled: readRequiredBooleanValue(record['tools_enabled'], 'Conversation MCP config response.tools_enabled'),
        toolApprovalRequired: readRequiredBooleanValue(record['tool_approval_required'], 'Conversation MCP config response.tool_approval_required'),
        knowledgeState: { blockingReason: blocking === null ? null : readRequiredEnumValue(blocking, 'Conversation MCP config response.knowledge_state.blocking_reason', MCP_BLOCKING_REASONS), ragEnabled: readRequiredBooleanValue(knowledge['rag_enabled'], 'Conversation MCP knowledge state.rag_enabled'), ready: readRequiredBooleanValue(knowledge['ready'], 'Conversation MCP knowledge state.ready'), forceToolsEnabled: readRequiredBooleanValue(knowledge['force_tools_enabled'], 'Conversation MCP knowledge state.force_tools_enabled'), toolsLocked: readRequiredBooleanValue(knowledge['tools_locked'], 'Conversation MCP knowledge state.tools_locked'), autoManaged: readRequiredBooleanValue(knowledge['auto_managed'], 'Conversation MCP knowledge state.auto_managed'), documentCount: readRequiredNonNegativeIntegerValue(knowledge['document_count'], 'Conversation MCP knowledge state.document_count') }
    };
};
const decodeMcpToolCatalog = (value: ApiResponsePayload): ConversationMcpToolCatalogResponse => {
    const record = requireRecord(value, 'Conversation MCP tool catalog response');
    const tools = requireJsonArray(record['tools'], 'Conversation MCP tool catalog response.tools').map((entry, index) => {
        const tool = requireRecord(entry, `Conversation MCP tool catalog response.tools[${String(index)}]`);
        return {
            name: requireString(tool['name'], 'Conversation MCP tool name'),
            definition: tool['definition'] === null ? null : tool['definition'] === undefined ? null : requireRecord(tool['definition'], 'Conversation MCP tool definition'),
            source: readRequiredEnumValue(tool['source'], 'Conversation MCP tool source', ['builtin', 'remote']),
            serverId: requireNullableString(tool['server_id'], 'Conversation MCP tool server_id'),
            serverName: requireString(tool['server_name'], 'Conversation MCP tool server_name'),
            allowed: readRequiredBooleanValue(tool['allowed'], 'Conversation MCP tool allowed'),
            blockedReason: requireNullableString(tool['blocked_reason'], 'Conversation MCP tool blocked_reason'),
            enabledByDefault: readRequiredBooleanValue(tool['enabled_by_default'], 'Conversation MCP tool enabled_by_default'),
            enabledByPlan: readRequiredBooleanValue(tool['enabled_by_plan'], 'Conversation MCP tool enabled_by_plan'),
            enabledByExecute: readRequiredBooleanValue(tool['enabled_by_execute'], 'Conversation MCP tool enabled_by_execute'),
            knowledgeRole: tool['knowledge_role'] === null ? null : readRequiredEnumValue(tool['knowledge_role'], 'Conversation MCP tool knowledge_role', ['required_access', 'management']),
            icons: tool['icons'] === null ? null : requireJsonArray(tool['icons'], 'Conversation MCP tool icons').map((icon, iconIndex) => requireRecord(icon, `Conversation MCP tool icons[${String(iconIndex)}]`))
        };
    });
    return { convId: requireString(record['conv_id'], 'Conversation MCP tool catalog response.conv_id'), tools, defaultTools: decodeStringList(record['default_tools'], 'Conversation MCP tool catalog response.default_tools'), planTools: decodeStringList(record['plan_tools'], 'Conversation MCP tool catalog response.plan_tools'), executeTools: decodeStringList(record['execute_tools'], 'Conversation MCP tool catalog response.execute_tools'), canonicalDefaultTools: decodeStringList(record['canonical_default_tools'], 'Conversation MCP tool catalog response.canonical_default_tools'), canonicalPlanTools: decodeStringList(record['canonical_plan_tools'], 'Conversation MCP tool catalog response.canonical_plan_tools'), canonicalExecuteTools: decodeStringList(record['canonical_execute_tools'], 'Conversation MCP tool catalog response.canonical_execute_tools') };
};
const decodePdfExportAccepted = (value: ApiResponsePayload): ConversationPdfExportAcceptedResponse => {
    const record = requireRecord(value, 'Conversation PDF export response');
    return { status: readRequiredEnumValue(record['status'], 'Conversation PDF export response.status', ['accepted']), taskId: requireString(record['task_id'], 'Conversation PDF export response.task_id'), commitDeadlineTsMs: record['commit_deadline_ts_ms'] === null || record['commit_deadline_ts_ms'] === undefined ? null : readRequiredEpochMsValue(record['commit_deadline_ts_ms'], 'Conversation PDF export response.commit_deadline_ts_ms'), downloadUrl: requireString(record['download_url'], 'Conversation PDF export response.download_url') };
};

export { decodeComparisonTurnPreflight, decodeInteractionFocus, decodeInteractionResolution, decodeMcpConfig, decodeMcpToolCatalog, decodePdfExportAccepted, decodePendingInteraction, decodePendingInteractions, decodeRawResponse, decodeSearchConfig, decodeSoaiLinkResolve, decodeSoaiOpen, decodeSoaiPathContentPart, decodeSoaiPreview, decodeSoaiRead, decodeSoaiToken, decodeStreamStatus, decodeWorkspacePathConfig };
export type {
    AskUserAnswerRequest,
    AskUserInteractionResolutionRequest,
    ComparisonTurnPreflightRequest,
    ComparisonTurnPreflightResponse,
    ComparisonTurnPreflightVariantResponse,
    ConversationAttentionRenderedRequest,
    ConversationInteractionEntry,
    ConversationInteractionFocusResponse,
    ConversationInteractionResolutionResponse,
    ConversationJsonExportRequest,
    ConversationMcpConfigResponse,
    ConversationMcpConfigUpdateRequest,
    ConversationMcpKnowledgeStateResponse,
    ConversationMcpToolCatalogResponse,
    ConversationMcpToolEntry,
    ConversationPendingInteractionResponse,
    ConversationPendingInteractionsResponse,
    ConversationPdfExportAcceptedResponse,
    ConversationPdfExportStartRequest,
    ConversationSearchConfigResponse,
    ConversationSearchConfigUpdateRequest,
    ConversationStreamStatusResponse,
    ConversationWorkspacePathConfigResponse,
    ConversationWorkspacePathConfigUpdateRequest,
    SecretPromptInteractionResolutionRequest,
    SoaiLinkResolveRecord,
    SoaiLinkResolveRequest,
    SoaiLinkResolveResponse,
    SoaiPathContentPart,
    SoaiPathOpenResponse,
    SoaiPathOperationRequest,
    SoaiPathPreviewEntry,
    SoaiPathPreviewResponse,
    SoaiPathReadResponse,
    SoaiPathTokenResponse,
    ToolApprovalInteractionResolutionRequest
};
