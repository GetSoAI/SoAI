/* SoAI - Chat page token counter validation [frontend/assets/ts/pages/chat/widgets/tokencounter/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ConversationUpdatedEvent } from '@core/realtime/eventcontracts/conversationContracts.ts';
import { normalizeConversationId } from '@features/chat/public.ts';

const normalizeTokenCounterId = (value: JsonValue): string | null => {
    const normalized = normalizeConversationId(value);
    return normalized ? normalized : null;
};

const isTokenCounterEventForConversation = (candidate: JsonValue, activeConversationId: string | null): boolean => {
    if (!activeConversationId) {
        return false;
    }
    return normalizeTokenCounterId(candidate) === activeConversationId;
};

const shouldRequestTokenCountForConversationEvent = (event: ConversationUpdatedEvent, activeConversationId: string | null): boolean => {
    return isTokenCounterEventForConversation(event.convId, activeConversationId) && (event.modelSettings !== undefined || event.messageCount !== undefined || event.settingsAuthorityChanged);
};

export { isTokenCounterEventForConversation, normalizeTokenCounterId, shouldRequestTokenCountForConversationEvent };
