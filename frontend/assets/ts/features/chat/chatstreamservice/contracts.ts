/* SoAI - Chat feature stream service boundary contracts [frontend/assets/ts/features/chat/chatstreamservice/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatStreamSession, StreamMutationType } from '@features/chat/chatstreamservice/types.ts';

interface StreamMutation {
    type: StreamMutationType;
    textDelta?: string | null;
}

interface StreamRuntime {
    notify: (session: ChatStreamSession, mutation?: StreamMutation | undefined) => void;
    notifyCheckpoint: (session: ChatStreamSession, mutation: StreamMutation) => Promise<void>;
    notifyUser: (session: ChatStreamSession) => void;
}

interface ChatPresentationInterests {
    acquireChatPresentationInterest(conversationId: string): string | null;
    updateChatPresentationInterest(token: string | null, conversationId: string): void;
    waitForChatPresentationInterest(token: string, conversationId: string): Promise<void>;
    releaseInterest(token: string | null): void;
}

interface ChatPresentationState {
    conversationId: string | null;
    visible: boolean;
}

export type { ChatPresentationInterests, ChatPresentationState, StreamMutation, StreamRuntime };
