/* SoAI - WebUI interaction request serialization [frontend/assets/ts/core/api/contracts/webuiInteractionSerialization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AskUserInteractionResolutionRequest, ConversationAttentionRenderedRequest, SecretPromptInteractionResolutionRequest, ToolApprovalInteractionResolutionRequest } from '@core/api/contracts/webuiChatOperationContractTypes.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

const serializeAskUserInteractionResolution = (request: AskUserInteractionResolutionRequest): JsonObject => {
    if (request.action === 'cancel') {
        return { action: 'cancel' };
    }
    const answers: JsonObject = {};
    for (const [questionId, answer] of Object.entries(request.answers)) {
        answers[questionId] = { answers: [...answer.answers] };
    }
    return { action: 'submit', answers };
};

const serializeSecretPromptInteractionResolution = (request: SecretPromptInteractionResolutionRequest): JsonObject => {
    if (request.action === 'cancel') {
        return { action: 'cancel' };
    }
    return {
        action: 'submit',
        username: request.username,
        password: request.password,
        'save_to_vault': request.saveToVault,
        label: request.label
    };
};

const serializeToolApprovalInteractionResolution = (request: ToolApprovalInteractionResolutionRequest): JsonObject => ({
    action: request.action,
    remember: request.remember
});

const serializeConversationAttentionRendered = (request: ConversationAttentionRenderedRequest): JsonObject => ({
    'interaction_type': request.interactionType,
    'task_id': request.taskId,
    'notification_id': request.notificationId
});

export { serializeAskUserInteractionResolution, serializeConversationAttentionRendered, serializeSecretPromptInteractionResolution, serializeToolApprovalInteractionResolution };
