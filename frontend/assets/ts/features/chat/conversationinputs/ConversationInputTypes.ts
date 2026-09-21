/* SoAI - Conversation input observation contracts [frontend/assets/ts/features/chat/conversationinputs/ConversationInputTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationInput, ConversationInputState, ConversationInputType } from '@core/api/contracts/chatQueueDraftContracts.ts';
import type { ConversationInputTerminalEvent, ConversationInputsChangedEvent } from '@core/realtime/eventcontracts/chatControlContracts.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { ChatPageApi } from '@features/chat/pagecontracts/types.ts';

interface ChatConversationInputsManagerDependencies {
    conversationInputsApi: ChatPageApi['webui']['chat']['inputQueue'];
    regenerationApi?: Pick<ChatPageApi['webui']['chat']['messages'], 'regenerate' | 'regenerationStatus'>;
    getCurrentConversationId: () => string | null;
    logWarning: (message: string, error?: Error) => void;
    updateInputQueuePreview: () => void;
    reconcileSettledConversationInputs: (conversationId: string) => Promise<void>;
    subscribeConversationInputEvents?: (listeners: { inputsChanged: (event: ConversationInputsChangedEvent) => void; inputTerminal: (event: ConversationInputTerminalEvent) => Promise<void> }) => (() => void) | null;
}

interface RetryableConversationRegeneration {
    inputId: string;
    acceptedAtMs: number;
    contentPreviewFeedback: JsonObject | null;
    previewContractFeedback: JsonObject | null;
}

export type { ConversationInput, ConversationInputState, ConversationInputType };
export type { ChatConversationInputsManagerDependencies, RetryableConversationRegeneration };
