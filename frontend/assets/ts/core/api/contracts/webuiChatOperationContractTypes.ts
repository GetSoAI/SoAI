/* SoAI - Frontend WebUI chat operation contract types [frontend/assets/ts/core/api/contracts/webuiChatOperationContractTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

interface ConversationInteractionEntry {
    taskId: string;
    interactionType: string;
    notificationId: string | null;
    createdAtMs: number;
    payload: JsonValue;
}
interface ConversationPendingInteractionsResponse {
    convId: string;
    interactions: ConversationInteractionEntry[];
}
interface ConversationPendingInteractionResponse {
    convId: string;
    interaction: ConversationInteractionEntry | null;
}
interface ConversationInteractionResolutionResponse {
    taskId: string;
    status: string;
}
interface ConversationInteractionFocusResponse {
    taskId: string;
    interactionType: 'ask_user' | 'tool_approval' | 'vault_secret_request';
}
interface AskUserAnswerRequest {
    answers: string[];
}
type AskUserInteractionResolutionRequest = { action: 'cancel' } | { action: 'submit'; answers: Record<string, AskUserAnswerRequest> };
type SecretPromptInteractionResolutionRequest = { action: 'cancel' } | { action: 'submit'; username: string | null; password: string; saveToVault: boolean; label: string | null };
interface ToolApprovalInteractionResolutionRequest {
    action: 'approve' | 'deny';
    remember: boolean;
}
interface ConversationAttentionRenderedRequest {
    interactionType: 'ask_user' | 'tool_approval' | 'vault_secret_request';
    taskId: string;
    notificationId: string;
}
interface ConversationStreamStatusResponse {
    active: boolean;
    conversationId: string;
    startAdmission: 'inactive' | 'busy' | 'unknown';
    streamLifecycle: 'inactive' | 'streaming' | 'terminalizing';
    canAcceptConversationInput: boolean;
    canStartNextPrompt: boolean;
    canAcceptSteerPrompt: boolean;
    activeToolCallCount: number;
    requestId?: string | undefined;
    assistantAtMs?: number | undefined;
    assistantTurnAtMs?: number | undefined;
    modelVariantIndex?: number | undefined;
    modelId?: string | undefined;
    previewKey?: string | undefined;
    previewArguments?: JsonObject | undefined;
    previewGeneratedAtMs?: number | undefined;
    previewCooldownMs?: number | undefined;
    previewTrigger?: string | undefined;
}
interface ComparisonTurnPreflightVariantResponse {
    modelVariantIndex: number;
    requestedModelId: string;
    resolvedModelId: string;
    assistantAtMs: number;
}
interface ComparisonTurnPreflightRequest {
    primaryModelId: string;
    comparisonModelIds: string[];
    minimumAssistantTurnAtMs?: number | undefined;
}
interface ComparisonTurnPreflightResponse {
    assistantTurnAtMs: number;
    variants: ComparisonTurnPreflightVariantResponse[];
}
interface SoaiPathSourceReference extends JsonObject {
    type: 'conversation_virtual_path';
    value: string;
}
interface SoaiPathToolReference extends JsonObject {
    type: 'workspace_relative_path';
    value: string;
}
interface SoaiPathWorkspaceScope extends JsonObject {
    type: 'conversation_effective_workspace';
    rootFingerprint: string;
}
interface SoaiPathTargetFingerprint extends JsonObject {
    type: 'file_sha256' | 'folder_listing_sha256';
    value: string;
}
interface SoaiPathContentPart extends JsonObject {
    type: 'soai_path';
    entryType: 'file' | 'folder';
    sourceReference: SoaiPathSourceReference;
    toolReference: SoaiPathToolReference;
    workspaceScope: SoaiPathWorkspaceScope;
    targetFingerprint: SoaiPathTargetFingerprint;
    title: string;
    previewType: string;
    mimeType: string | null;
    sizeBytes: number | null;
    modifiedAtMs: number;
    resolvedAtMs: number;
}
interface SoaiPathUnavailableResponse {
    state: 'unavailable';
}
interface SoaiPathPreviewEntry {
    name: string;
    entryType: 'file' | 'folder';
    sizeBytes: number;
    modifiedAtMs: number;
}
interface SoaiPathPreviewAvailableResponse {
    state: 'available';
    contentPart: SoaiPathContentPart;
    entries?: SoaiPathPreviewEntry[] | undefined;
}
interface SoaiPathReadAvailableResponse {
    state: 'available';
    contentPart: SoaiPathContentPart;
    text: string;
}
interface SoaiPathOpenAvailableResponse {
    state: 'available';
    virtualPath: string;
}
interface SoaiPathTokenAvailableResponse {
    state: 'available';
    token: string;
}
type SoaiPathPreviewResponse = SoaiPathUnavailableResponse | SoaiPathPreviewAvailableResponse;
type SoaiPathReadResponse = SoaiPathUnavailableResponse | SoaiPathReadAvailableResponse;
type SoaiPathOpenResponse = SoaiPathUnavailableResponse | SoaiPathOpenAvailableResponse;
type SoaiPathTokenResponse = SoaiPathUnavailableResponse | SoaiPathTokenAvailableResponse;
interface SoaiLinkResolveRecord {
    token: string;
    occurrenceIndex: number;
    displayLabel: string | null;
    contentPart: SoaiPathContentPart;
}
interface SoaiLinkResolveResponse {
    records: SoaiLinkResolveRecord[];
    tokenCount: number;
}
interface SoaiLinkResolveRequest {
    rawText: string;
}
interface SoaiPathOperationRequest {
    contentPart?: SoaiPathContentPart | undefined;
    sourceReference?: SoaiPathSourceReference | undefined;
    workspaceScope?: SoaiPathWorkspaceScope | undefined;
}

interface SoaiPathBrowseRequest {
    query: string | null;
    limit: number;
}
interface ConversationWorkspacePathConfigResponse {
    convId: string;
    workspacePath: string | null;
    effectiveWorkspacePath: string | null;
    effectiveRootFingerprint: string | null;
    isValid: boolean;
    validationCode: string | null;
    validationMessage: string | null;
}
interface ConversationWorkspacePathConfigUpdateRequest {
    workspacePath: string | null;
}
interface ConversationSearchConfigResponse {
    enabled: boolean;
    defaultProvider: string | null;
    maxResults: number;
    availableProviders: string[];
}
interface ConversationSearchConfigUpdateRequest {
    enabled?: boolean | null;
    defaultProvider?: string | null;
    maxResults?: number | null;
}
interface ConversationMcpKnowledgeStateResponse {
    blockingReason: 'disabled' | 'empty' | 'model_without_tool_calling' | 'missing_required_tools' | null;
    ragEnabled: boolean;
    ready: boolean;
    forceToolsEnabled: boolean;
    toolsLocked: boolean;
    autoManaged: boolean;
    documentCount: number;
}
interface ConversationMcpConfigResponse {
    convId: string;
    defaultTools: string[];
    planTools: string[];
    executeTools: string[];
    serverConfigs: Record<string, boolean>;
    toolsEnabled: boolean;
    toolApprovalRequired: boolean;
    knowledgeState: ConversationMcpKnowledgeStateResponse;
}
interface ConversationMcpConfigUpdateRequest {
    defaultTools?: string[] | null;
    planTools?: string[] | null;
    executeTools?: string[] | null;
    serverConfigs?: Record<string, boolean> | null;
    toolsEnabled?: boolean | null;
    toolApprovalRequired?: boolean | null;
}
interface ConversationMcpToolEntry {
    name: string;
    definition: JsonObject | null;
    source: 'builtin' | 'remote';
    serverId: string | null;
    serverName: string;
    allowed: boolean;
    blockedReason: string | null;
    enabledByDefault: boolean;
    enabledByPlan: boolean;
    enabledByExecute: boolean;
    knowledgeRole: 'required_access' | 'management' | null;
    icons: JsonObject[] | null;
}
interface ConversationMcpToolCatalogResponse {
    convId: string;
    tools: ConversationMcpToolEntry[];
    defaultTools: string[];
    planTools: string[];
    executeTools: string[];
    canonicalDefaultTools: string[];
    canonicalPlanTools: string[];
    canonicalExecuteTools: string[];
}
interface ConversationPdfExportAcceptedResponse {
    status: 'accepted';
    taskId: string;
    commitDeadlineTsMs: number | null;
    downloadUrl: string;
}
interface ConversationPdfExportStartRequest {
    sizeBytes: string;
    title: string;
    exportDate: string;
    smallLogoDataUri: string;
    conversationId: string;
    expectedLastModifiedAtMs: string;
    coverHtml: string;
    coverSha256: string;
    footerNoteLabel: string;
    footerPagesLabel: string;
    htmlSha256: string;
}
interface ConversationJsonExportRequest {
    activeModel: string | null;
    parameters: JsonObject;
}

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
    SoaiPathBrowseRequest,
    SoaiPathContentPart,
    SoaiPathOpenResponse,
    SoaiPathOperationRequest,
    SoaiPathPreviewEntry,
    SoaiPathPreviewResponse,
    SoaiPathReadResponse,
    SoaiPathTokenResponse,
    ToolApprovalInteractionResolutionRequest
};
