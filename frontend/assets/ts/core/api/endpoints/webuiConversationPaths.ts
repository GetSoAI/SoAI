/* SoAI - Shared API WebUI conversation paths [frontend/assets/ts/core/api/endpoints/webuiConversationPaths.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import type { ApiPathSegmentValue } from '@core/api/types/request.ts';
import { encodeSegment } from '@core/identifiers.ts';
import { stableJsonStringify } from '@core/serialization/json.ts';
import type { SoaiPathContentPart } from '@core/api/contracts/webuiChatOperationContracts.ts';
import { serializeSoaiPathContentPart } from '@core/api/contracts/webuiSoaiPathSerialization.ts';

type WebuiConversationInteraction = 'ask_user' | 'vault_secret_request' | 'tool_approval';

const WEBUI_CONVERSATIONS_BASE_PATH = '/api/v1/webui/conversations';

const buildWebuiConversationBasePath = (id: string): string => `${WEBUI_CONVERSATIONS_BASE_PATH}/${encodeSegment(id.trim())}`;
const buildWebuiConversationAttachmentContentPath = (id: string, attachmentId: string, download: boolean): string => `${buildWebuiConversationBasePath(id)}/attachments/${encodeSegment(attachmentId.trim())}/content?download=${download ? '1' : '0'}`;
const buildWebuiConversationAttachmentThumbnailPath = (id: string, attachmentId: string): string => `${buildWebuiConversationBasePath(id)}/attachments/${encodeSegment(attachmentId.trim())}/content?download=0&thumbnail=1`;
const buildWebuiConversationKnowledgeAttachmentPath = (id: string, knowledgeAttachmentId: string): string => `${buildWebuiConversationBasePath(id)}/knowledge-attachments/${encodeSegment(knowledgeAttachmentId.trim())}`;
const buildWebuiConversationKnowledgeAttachmentItemsPath = (id: string, knowledgeAttachmentId: string): string => `${buildWebuiConversationKnowledgeAttachmentPath(id, knowledgeAttachmentId)}/items`;
const buildWebuiConversationKnowledgeAttachmentItemsQueryPath = (id: string, knowledgeAttachmentId: string): string => `${buildWebuiConversationKnowledgeAttachmentItemsPath(id, knowledgeAttachmentId)}/query`;
const buildWebuiConversationKnowledgeAttachmentItemPreviewPath = (id: string, knowledgeAttachmentId: string, itemId: string): string => `${buildWebuiConversationKnowledgeAttachmentItemsPath(id, knowledgeAttachmentId)}/${encodeSegment(itemId.trim())}/preview`;
const buildWebuiConversationAbsolutePathsResolvePath = (id: string): string => `${buildWebuiConversationBasePath(id)}/absolute-paths/resolve`;
const buildWebuiConversationSoaiLinksResolvePath = (id: string): string => `${buildWebuiConversationBasePath(id)}/soai-links/resolve`;
const buildWebuiConversationSoaiPathsOperationPath = (id: string, operation: string): string => `${buildWebuiConversationBasePath(id)}/soai-paths/${encodeSegment(operation.trim())}`;
const buildWebuiConversationSoaiPathContentPath = (id: string, contentPart: SoaiPathContentPart, download: boolean): string => `${buildWebuiConversationBasePath(id)}/soai-paths/content?content_part=${encodeURIComponent(stableJsonStringify(serializeSoaiPathContentPart(contentPart)))}&download=${download ? '1' : '0'}`;
const buildWebuiConversationSoaiPathThumbnailPath = (id: string, contentPart: SoaiPathContentPart): string => `${buildWebuiConversationBasePath(id)}/soai-paths/content?content_part=${encodeURIComponent(stableJsonStringify(serializeSoaiPathContentPart(contentPart)))}&download=0&thumbnail=1`;

interface WebuiConversationPaths {
    base(id: string): string;
    clone(id: string): string;
    interactionsPending(id: string, interaction: WebuiConversationInteraction): string;
    interactionsResolve(id: string, interaction: WebuiConversationInteraction, taskId: string): string;
    interactionFocus(id: string, focusNonce: string): string;
    attentionRendered(id: string): string;
    messages(id: string): string;
    messageWindow(id: string): string;
    messageSyncCursor(id: string): string;
    messageRunningActivity(id: string): string;
    messageResubmit(id: string): string;
    messageDelete(id: string): string;
    messageRegenerate(id: string): string;
    messageRegenerationStatus(id: string, clientId?: string, clientRequestId?: string): string;
    jsonExport(id: string): string;
    streamStatus(id: string): string;
    streamCancel(id: string): string;
    assistantTurnStreamState(id: string, assistantTurnAtMs: number, modelVariantIndex: number): string;
    comparisonPreflight(id: string): string;
    title(id: string): string;
    settings(id: string): string;
    color(id: string): string;
    favorite(id: string): string;
    archived(id: string): string;
    archivedList(): string;
    archivedSearch(): string;
    workspacePath(id: string): string;
    agentTurnCancel(id: string, turnId: string): string;
    agentCompactStart(id: string): string;
    agentCompactRegenerate(id: string): string;
    agentCompactRemoveBoundary(id: string): string;
    agentShellToolStop(id: string): string;
    agentTodo(id: string): string;
    agentPlan(id: string): string;
    inputQueue(id: string): string;
    inputQueuePrompt(id: string, promptId: string): string;
    draft(id: string): string;
    ragConfig(id: string): string;
    ragDocuments(id: string): string;
    ragDocumentsBatch(id: string): string;
    ragIngestFileExplorer(id: string): string;
    ragDocument(id: string, documentId: string): string;
    ragReindex(id: string): string;
    attachments(id: string): string;
    attachment(id: string, attachmentId: string): string;
    attachmentContent(id: string, attachmentId: string, download: boolean): string;
    knowledgeAttachmentsDraft(id: string): string;
    knowledgeAttachmentsClaim(id: string): string;
    knowledgeAttachment(id: string, knowledgeAttachmentId: string): string;
    knowledgeAttachmentCancel(id: string, knowledgeAttachmentId: string): string;
    knowledgeAttachmentItems(id: string, knowledgeAttachmentId: string): string;
    knowledgeAttachmentItemsQuery(id: string, knowledgeAttachmentId: string): string;
    knowledgeAttachmentItemPreview(id: string, knowledgeAttachmentId: string, itemId: string): string;
    knowledgeAttachmentsUse(id: string): string;
    absolutePathsResolve(id: string): string;
    soaiLinksResolve(id: string): string;
    soaiPathsPreview(id: string): string;
    soaiPathsBrowse(id: string): string;
    soaiPathsRead(id: string): string;
    soaiPathsDownload(id: string): string;
    soaiPathContent(id: string, contentPart: SoaiPathContentPart, download: boolean): string;
    soaiPathThumbnail(id: string, contentPart: SoaiPathContentPart): string;
    soaiPathsOpen(id: string): string;
    soaiPathsToken(id: string): string;
    searchConfig(id: string): string;
    mcpTools(id: string): string;
    mcpConfig(id: string): string;
}

const createWebuiConversationPaths = (api: ApiClientContext): WebuiConversationPaths => {
    const encode = (value: ApiPathSegmentValue): string => api.encodePathSegment(value);
    const base = (id: string): string => buildWebuiConversationBasePath(id);

    return {
        base,
        clone: (id): string => `${base(id)}/clone`,
        interactionsPending: (id, interaction): string => `${base(id)}/interactions/${interaction}/pending`,
        interactionsResolve: (id, interaction, taskId): string => `${base(id)}/interactions/${interaction}/${encode(taskId)}/resolve`,
        interactionFocus: (id, focusNonce): string => `${base(id)}/interactions/focus?interaction_focus=${encodeURIComponent(focusNonce.trim())}`,
        attentionRendered: (id): string => `${base(id)}/attention/rendered`,
        messages: (id): string => `${base(id)}/messages`,
        messageWindow: (id): string => `${base(id)}/messages/window`,
        messageSyncCursor: (id): string => `${base(id)}/messages/sync-cursor`,
        messageRunningActivity: (id): string => `${base(id)}/messages/running-activity`,
        messageResubmit: (id): string => `${base(id)}/messages/resubmit`,
        messageDelete: (id): string => `${base(id)}/messages/delete`,
        messageRegenerate: (id): string => `${base(id)}/messages/regenerate`,
        messageRegenerationStatus: (id, clientId, clientRequestId): string => {
            const path = `${base(id)}/messages/regenerate/status`;
            if (!clientId || !clientRequestId) return path;
            return `${path}?client_id=${encodeURIComponent(clientId)}&client_request_id=${encodeURIComponent(clientRequestId)}`;
        },
        jsonExport: (id): string => `${base(id)}/export/json`,
        streamStatus: (id): string => `${base(id)}/stream-status`,
        streamCancel: (id): string => `${base(id)}/stream/cancel`,
        assistantTurnStreamState: (id, assistantTurnAtMs, modelVariantIndex): string => `${base(id)}/assistant-turns/${encode(assistantTurnAtMs)}/variants/${encode(modelVariantIndex)}/stream-state`,
        comparisonPreflight: (id): string => `${base(id)}/comparison-turns/preflight`,
        title: (id): string => `${base(id)}/title`,
        settings: (id): string => `${base(id)}/settings`,
        color: (id): string => `${base(id)}/color`,
        favorite: (id): string => `${base(id)}/favorite`,
        archived: (id): string => `${base(id)}/archived`,
        archivedList: (): string => `${WEBUI_CONVERSATIONS_BASE_PATH}/archived`,
        archivedSearch: (): string => `${WEBUI_CONVERSATIONS_BASE_PATH}/archived/search`,
        workspacePath: (id): string => `${base(id)}/workspace-path`,
        agentTurnCancel: (id, turnId): string => `${base(id)}/agent/turns/${encode(turnId)}/cancel`,
        agentCompactStart: (id): string => `${base(id)}/agent/compact/start`,
        agentCompactRegenerate: (id): string => `${base(id)}/agent/compact/regenerate`,
        agentCompactRemoveBoundary: (id): string => `${base(id)}/agent/compact/remove-boundary`,
        agentShellToolStop: (id): string => `${base(id)}/agent/tools/shell/stop`,
        agentTodo: (id): string => `${base(id)}/agent/todo`,
        agentPlan: (id): string => `${base(id)}/agent/plan`,
        inputQueue: (id): string => `${base(id)}/input-queue`,
        inputQueuePrompt: (id, promptId): string => `${base(id)}/input-queue/${encode(promptId)}`,
        draft: (id): string => `${base(id)}/draft`,
        ragConfig: (id): string => `${base(id)}/rag/config`,
        ragDocuments: (id): string => `${base(id)}/rag/documents`,
        ragDocumentsBatch: (id): string => `${base(id)}/rag/documents/batch`,
        ragIngestFileExplorer: (id): string => `${base(id)}/rag/ingest-file-explorer`,
        ragDocument: (id, documentId): string => `${base(id)}/rag/documents/${encode(documentId)}`,
        ragReindex: (id): string => `${base(id)}/rag/reindex`,
        attachments: (id): string => `${base(id)}/attachments`,
        attachment: (id, attachmentId): string => `${base(id)}/attachments/${encode(attachmentId)}`,
        attachmentContent: buildWebuiConversationAttachmentContentPath,
        knowledgeAttachmentsDraft: (id): string => `${base(id)}/knowledge-attachments/draft`,
        knowledgeAttachmentsClaim: (id): string => `${base(id)}/knowledge-attachments/claim`,
        knowledgeAttachment: buildWebuiConversationKnowledgeAttachmentPath,
        knowledgeAttachmentCancel: (id, knowledgeAttachmentId): string => `${buildWebuiConversationKnowledgeAttachmentPath(id, knowledgeAttachmentId)}/cancel`,
        knowledgeAttachmentItems: buildWebuiConversationKnowledgeAttachmentItemsPath,
        knowledgeAttachmentItemsQuery: buildWebuiConversationKnowledgeAttachmentItemsQueryPath,
        knowledgeAttachmentItemPreview: buildWebuiConversationKnowledgeAttachmentItemPreviewPath,
        knowledgeAttachmentsUse: (id): string => `${base(id)}/knowledge-attachments/use`,
        absolutePathsResolve: buildWebuiConversationAbsolutePathsResolvePath,
        soaiLinksResolve: buildWebuiConversationSoaiLinksResolvePath,
        soaiPathsBrowse: (id): string => buildWebuiConversationSoaiPathsOperationPath(id, 'browse'),
        soaiPathsPreview: (id): string => buildWebuiConversationSoaiPathsOperationPath(id, 'preview'),
        soaiPathsRead: (id): string => buildWebuiConversationSoaiPathsOperationPath(id, 'read'),
        soaiPathsDownload: (id): string => buildWebuiConversationSoaiPathsOperationPath(id, 'download'),
        soaiPathContent: buildWebuiConversationSoaiPathContentPath,
        soaiPathThumbnail: buildWebuiConversationSoaiPathThumbnailPath,
        soaiPathsOpen: (id): string => buildWebuiConversationSoaiPathsOperationPath(id, 'open'),
        soaiPathsToken: (id): string => buildWebuiConversationSoaiPathsOperationPath(id, 'token'),
        searchConfig: (id): string => `${base(id)}/search/config`,
        mcpTools: (id): string => `${base(id)}/mcp/tools`,
        mcpConfig: (id): string => `${base(id)}/mcp/config`
    };
};

export { buildWebuiConversationAttachmentContentPath, buildWebuiConversationAttachmentThumbnailPath, buildWebuiConversationKnowledgeAttachmentItemPreviewPath, buildWebuiConversationKnowledgeAttachmentItemsPath, buildWebuiConversationKnowledgeAttachmentPath, buildWebuiConversationAbsolutePathsResolvePath, buildWebuiConversationSoaiLinksResolvePath, buildWebuiConversationSoaiPathContentPath, buildWebuiConversationSoaiPathThumbnailPath, buildWebuiConversationSoaiPathsOperationPath, createWebuiConversationPaths };
export type { WebuiConversationInteraction, WebuiConversationPaths };
