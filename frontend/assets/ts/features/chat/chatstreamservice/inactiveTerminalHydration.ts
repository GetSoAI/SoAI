/* SoAI - Inactive chat stream terminal hydration [frontend/assets/ts/features/chat/chatstreamservice/inactiveTerminalHydration.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { AssistantStreamStateIdentity } from '@features/chat/chatstreamservice/assistantStreamStatePayload.ts';
import { waitForAssistantStreamStateSnapshot } from '@features/chat/chatstreamservice/assistantStreamStateHydration.ts';
import type { ChatStreamApiClient } from '@features/chat/chatstreamservice/chatStreamApi.ts';

type InactiveTerminalHydrationIdentity = AssistantStreamStateIdentity & {
    conversationId: string;
};

const waitForInactiveTerminalAssistantState = async (inputArguments: { apiClient: ChatStreamApiClient; identity: InactiveTerminalHydrationIdentity; initialMessage: ChatMessage | null; shouldContinue: () => boolean; signal?: AbortSignal | undefined }): Promise<ChatMessage | null> => {
    return await waitForAssistantStreamStateSnapshot({
        apiClient: inputArguments.apiClient,
        identity: inputArguments.identity,
        initialMessage: inputArguments.initialMessage,
        requireTerminal: true,
        shouldContinue: inputArguments.shouldContinue,
        signal: inputArguments.signal
    });
};

export { waitForInactiveTerminalAssistantState };
export type { InactiveTerminalHydrationIdentity };
