/* SoAI - Chat page secret prompt resolution controller [frontend/assets/ts/pages/chat/controllers/chatpage/construction/secretPromptResolutionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SecretPromptInteractionResolutionRequest } from '@core/api/contracts/webuiChatOperationContracts.ts';
import { i18n } from '@core/i18n/index.ts';
import { CHAT_VALIDATION_NOTIFICATION_DURATION_MS, normalizeResolutionIds } from '@pages/chat/controllers/chatpage/construction/elicitation/guards.ts';
import type { ChatElicitationSession } from '@features/chat/public.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';

interface SecretPromptResolutionHost extends PageFeedbackOwnerHost {
    elicitation: ChatElicitationSession;
    updateInputState(): void;
}

async function resolveSecretPromptForConstruction(host: SecretPromptResolutionHost, conversationId: string, taskId: string, request: SecretPromptInteractionResolutionRequest): Promise<void> {
    const normalized = normalizeResolutionIds(conversationId, taskId);
    if (!normalized) {
        return;
    }
    const { conversationId: normalizedConversationId, taskId: normalizedTaskId } = normalized;
    const elicitation = host.elicitation;
    const prompt = elicitation.getSecretPrompt(normalizedConversationId);
    if (!prompt || prompt.taskId !== normalizedTaskId) {
        return;
    }
    if (request.action === 'submit') {
        if (request.password === '') {
            host.feedback.show(i18n.t('chat.secretPrompt.validationPasswordRequired'), 'warning', CHAT_VALIDATION_NOTIFICATION_DURATION_MS);
            return;
        }
        if (request.saveToVault) {
            if (!prompt.allowSaveToVault) {
                host.feedback.show(i18n.t('chat.secretPrompt.validationSaveNotAllowed'), 'warning', CHAT_VALIDATION_NOTIFICATION_DURATION_MS);
                return;
            }
            if (!request.label?.trim()) {
                host.feedback.show(i18n.t('chat.secretPrompt.validationLabelRequired'), 'warning', CHAT_VALIDATION_NOTIFICATION_DURATION_MS);
                return;
            }
        }
    }
    await elicitation.resolveSecretPrompt(normalizedConversationId, normalizedTaskId, request);
    host.updateInputState();
}

export { resolveSecretPromptForConstruction };
