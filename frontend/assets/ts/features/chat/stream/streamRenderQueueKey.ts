/* SoAI - Stable queue keys for coalesced chat stream renders [frontend/assets/ts/features/chat/stream/streamRenderQueueKey.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNonNegativeInteger } from '@core/typeGuards.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

const resolveNonNegativeIntegerText = (value: number | null | undefined): string => (isNonNegativeInteger(value) ? String(value) : '');

const resolveStreamRenderQueueKey = (message: ChatMessage, conversationId: string): string => {
    const messageId = typeof message.id === 'string' || typeof message.id === 'number' ? String(message.id) : '';
    return [normalizeConversationId(conversationId), resolveNonNegativeIntegerText(message.assistantTurnAtMs), resolveNonNegativeIntegerText(message.modelVariantIndex), resolveNonNegativeIntegerText(message.timestamp), messageId].join('|');
};

export { resolveStreamRenderQueueKey };
