/* SoAI - Authenticated Messaging interaction focus lifecycle [frontend/assets/ts/pages/chat/controllers/page/interactionFocusController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationInteractionFocusResponse } from '@core/api/contracts/webuiChatOperationContracts.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

interface InteractionFocusHost {
    resolveInteractionFocus(conversationId: string, focusNonce: string): Promise<ConversationInteractionFocusResponse>;
    focusInteraction(conversationId: string, interactionType: ConversationInteractionFocusResponse['interactionType'], taskId: string): void;
    showUnavailable(): void;
    logWarning(error: Error): void;
}

const applyInteractionFocus = async (host: InteractionFocusHost, parameters: JsonObject, conversationId: string | null, signal: AbortSignal): Promise<void> => {
    const nonceValue = parameters['interaction_focus'];
    const focusNonce = typeof nonceValue === 'string' ? nonceValue.trim() : '';
    if (!focusNonce || !conversationId || signal.aborted) return;
    try {
        const focus = await host.resolveInteractionFocus(conversationId, focusNonce);
        if (signal.aborted) return;
        host.focusInteraction(conversationId, focus.interactionType, focus.taskId);
    } catch (error) {
        if (signal.aborted) return;
        host.logWarning(ensureError(error));
        host.showUnavailable();
    }
};

const interactionFocusUnavailableText = (): string => i18n.t('chat.errors.interactionFocusUnavailable');

export { applyInteractionFocus, interactionFocusUnavailableText };
export type { InteractionFocusHost };
