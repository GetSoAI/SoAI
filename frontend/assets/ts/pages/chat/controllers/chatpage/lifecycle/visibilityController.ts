/* SoAI - Chat page visibility controller [frontend/assets/ts/pages/chat/controllers/chatpage/lifecycle/visibilityController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { sleepMs } from '@core/primitives/sleepMs.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatConversationViewHost } from '@pages/chat/controllers/chatpage/conversations/contracts.ts';

interface ChatPageHideVisibilityHost {
    saveStorageState(): void;
    stopVoiceCallIfHidden(): Promise<void>;
    disposeAudioManager(): void;
    stopTtsManager(): void;
    clearViewportResizeCleanup(): void;
}

interface ChatPageShowVisibilityHost extends ChatConversationStateHost, ChatConversationViewHost {
    signal: AbortSignal;
    clearViewportResizeCleanup(): void;
    syncResponsiveLayout(): void;
    attachViewportResize(handler: () => void, options: { debounceMs: number }): () => void;
    setViewportResizeCleanup(cleanup: (() => void) | null): void;
}

const suspendChatPageVisibilityRuntime = async (host: ChatPageHideVisibilityHost): Promise<void> => {
    host.saveStorageState();
    await host.stopVoiceCallIfHidden();
    host.disposeAudioManager();
    host.stopTtsManager();
    host.clearViewportResizeCleanup();
};

const resumeChatPageVisibilityRuntime = async (host: ChatPageShowVisibilityHost): Promise<void> => {
    if (host.signal.aborted) {
        return;
    }
    host.clearViewportResizeCleanup();
    host.setViewportResizeCleanup(host.attachViewportResize(() => host.syncResponsiveLayout(), { debounceMs: 150 }));
    host.syncResponsiveLayout();
    const conversationId = host.conversationState.currentConversationId;
    if (conversationId && !host.signal.aborted) {
        await host.conversationView.replaceRoute(conversationId, { signal: host.signal });
    }
    await sleepMs(0);
    if (host.signal.aborted) return;
    await sleepMs(0);
    if (host.signal.aborted) return;
    await sleepMs(0);
};

export { resumeChatPageVisibilityRuntime, suspendChatPageVisibilityRuntime };
