/* SoAI - Chat page conversation hydration state [frontend/assets/ts/pages/chat/state/chatConversationHydrationState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type SelectedConversationHydrationStatus = 'idle' | 'loading' | 'error';

interface SelectedConversationHydrationState {
    conversationId: string | null;
    status: SelectedConversationHydrationStatus;
}

const IDLE_SELECTED_CONVERSATION_HYDRATION_STATE: SelectedConversationHydrationState = {
    conversationId: null,
    status: 'idle'
};

export { IDLE_SELECTED_CONVERSATION_HYDRATION_STATE };
export type { SelectedConversationHydrationState, SelectedConversationHydrationStatus };
