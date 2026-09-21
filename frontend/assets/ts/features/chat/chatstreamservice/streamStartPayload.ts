/* SoAI - Chat stream start WebSocket payload construction [frontend/assets/ts/features/chat/chatstreamservice/streamStartPayload.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';
import { WEBSOCKET_MESSAGE_TYPES } from '@core/websocketEvents.ts';
import type { ContentPreviewFeedbackPayload, PreviewContractViolationFeedbackPayload } from '@features/chat/contentPreviewContracts.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';

const serializeContentPreviewFeedback = (feedback: ContentPreviewFeedbackPayload): JsonObject => ({
    'assistant_at_ms': feedback.assistantAtMs,
    'assistant_turn_at_ms': feedback.assistantTurnAtMs,
    items: feedback.items.map((item) => ({
        'reference_type': item.referenceType,
        target: item.target,
        status: item.status,
        'reason_code': item.reasonCode
    }))
});

const serializePreviewContractFeedback = (feedback: PreviewContractViolationFeedbackPayload): JsonObject => ({
    'assistant_at_ms': feedback.assistantAtMs,
    'assistant_turn_at_ms': feedback.assistantTurnAtMs,
    code: feedback.code,
    'reason_code': feedback.reasonCode,
    detail: feedback.detail,
    'repair_attempted': feedback.repairAttempted,
    'repair_succeeded': feedback.repairSucceeded
});

const buildChatStreamStartPayload = (inputArguments: { session: ChatStreamSession; requestBody: JsonObject; contentPreviewFeedback: ContentPreviewFeedbackPayload | null; previewContractFeedback: PreviewContractViolationFeedbackPayload | null }): JsonObject => {
    const startPayload: JsonObject = {
        type: WEBSOCKET_MESSAGE_TYPES.CHAT_STREAM_START,
        'conv_id': inputArguments.session.conversationId,
        'request_id': inputArguments.session.requestId,
        'assistant_at_ms': inputArguments.session.assistantTimestamp,
        'assistant_turn_at_ms': inputArguments.session.assistantTurnTimestamp,
        'model_variant_index': inputArguments.session.modelVariantIndex,
        'openai_request': inputArguments.requestBody
    };
    if (inputArguments.contentPreviewFeedback !== null) {
        startPayload['content_preview_feedback'] = serializeContentPreviewFeedback(inputArguments.contentPreviewFeedback);
    }
    if (inputArguments.previewContractFeedback !== null) {
        startPayload['preview_contract_feedback'] = serializePreviewContractFeedback(inputArguments.previewContractFeedback);
    }
    return startPayload;
};

export { buildChatStreamStartPayload, serializeContentPreviewFeedback, serializePreviewContractFeedback };
