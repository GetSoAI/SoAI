/* SoAI - Chat page lifecycle resource ownership [frontend/assets/ts/pages/chat/state/ChatLifecycleResourceManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AudioState } from '@features/chat/public.ts';
import type { HeaderActionController } from '@core/headerActionBus.ts';
import type { ChatUiTaskScopeContract } from '@pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts';

class ChatLifecycleResources {
    presenceExit: (() => void) | null = null;
    activePresenceExit: (() => void) | null = null;
    presentationPresenceExit: (() => void) | null = null;
    terminalIndicatorsExit: (() => void) | null = null;
    terminalRenderAcknowledgerExit: (() => void) | null = null;
    streamPresentationExit: (() => void) | null = null;
    chatActivityExit: (() => void) | null = null;
    detachAction: HeaderActionController | null = null;
    autoSaveCleanup: (() => void) | null = null;
    microphoneAudioState: AudioState = 'idle';
    #viewportResizeCleanup: (() => void) | null = null;
    #afterInitializeAbortController: AbortController | null = null;
    #destroyed = false;

    get isDestroyed(): boolean {
        return this.#destroyed;
    }

    beginDestroy(taskScope: ChatUiTaskScopeContract): void {
        if (this.#destroyed) {
            return;
        }
        this.#destroyed = true;
        this.chatActivityExit?.();
        this.chatActivityExit = null;
        this.cancelPageUi(taskScope);
    }

    cancelPageUi(taskScope: ChatUiTaskScopeContract): void {
        this.suspendStreamPresentation();
        this.#afterInitializeAbortController?.abort();
        this.#afterInitializeAbortController = null;
        taskScope.concurrency.clearConversationActivation();
        taskScope.concurrency.beginRenderSequence('conversation-current');
        taskScope.concurrency.beginRenderSequence('conversation-list');
        taskScope.concurrency.beginRenderSequence('memory-tab-refresh');
        this.clearViewportResizeCleanup();
    }

    suspendStreamPresentation(): void {
        this.streamPresentationExit?.();
        this.streamPresentationExit = null;
    }

    resetAfterInitializeAbortController(): void {
        this.#afterInitializeAbortController?.abort();
        this.#afterInitializeAbortController = new AbortController();
    }

    getAfterInitializeAbortController(): AbortController | null {
        return this.#afterInitializeAbortController;
    }

    setViewportResizeCleanup(cleanup: (() => void) | null): void {
        this.#viewportResizeCleanup = cleanup;
    }

    clearViewportResizeCleanup(): void {
        this.#viewportResizeCleanup?.();
        this.#viewportResizeCleanup = null;
    }
}

export { ChatLifecycleResources };
export interface ChatLifecycleResourcesHost {
    lifecycleResources: ChatLifecycleResources;
}
