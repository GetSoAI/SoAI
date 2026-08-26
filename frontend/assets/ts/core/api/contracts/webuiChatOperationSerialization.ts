/* SoAI - WebUI chat operation request serialization [frontend/assets/ts/core/api/contracts/webuiChatOperationSerialization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ComparisonTurnPreflightRequest, ConversationJsonExportRequest, ConversationPdfExportStartRequest } from '@core/api/contracts/webuiChatOperationContractTypes.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

const serializeComparisonTurnPreflight = (request: ComparisonTurnPreflightRequest): JsonObject => {
    const serialized: JsonObject = {
        'primary_model_id': request.primaryModelId,
        'comparison_model_ids': request.comparisonModelIds
    };
    if (request.minimumAssistantTurnAtMs !== undefined) {
        serialized['minimum_assistant_turn_at_ms'] = request.minimumAssistantTurnAtMs;
    }
    return serialized;
};

const serializeConversationJsonExport = (request: ConversationJsonExportRequest): JsonObject => ({
    'active_model': request.activeModel,
    parameters: request.parameters
});

const serializeConversationPdfExportStart = (request: ConversationPdfExportStartRequest): Record<string, string | Blob> => ({
    'size_bytes': request.sizeBytes,
    title: request.title,
    'export_date': request.exportDate,
    'small_logo_data_uri': request.smallLogoDataUri,
    'conversation_id': request.conversationId,
    'expected_last_modified_at_ms': request.expectedLastModifiedAtMs,
    'cover_html': request.coverHtml,
    'cover_sha256': request.coverSha256,
    'footer_note_label': request.footerNoteLabel,
    'footer_pages_label': request.footerPagesLabel,
    'html_sha256': request.htmlSha256
});

export { serializeComparisonTurnPreflight, serializeConversationJsonExport, serializeConversationPdfExportStart };
