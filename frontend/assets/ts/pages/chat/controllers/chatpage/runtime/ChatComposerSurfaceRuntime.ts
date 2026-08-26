/* SoAI - Chat composer UI and attachment lifecycle ownership [frontend/assets/ts/pages/chat/controllers/chatpage/runtime/ChatComposerSurfaceRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatAttachmentManager, ChatUIManager } from '@features/chat/public.ts';
import type { ComposerSoaiLinkResolutionManager } from '@pages/chat/controllers/chatmessagesendingcontroller/composerSoaiLinkResolutionManager.ts';

class ChatComposerSurfaceRuntime {
    #ui: ChatUIManager | null = null;
    #attachments: ChatAttachmentManager | null = null;
    #soaiLinkResolution: ComposerSoaiLinkResolutionManager | null = null;

    initializeSoaiLinkResolution(manager: ComposerSoaiLinkResolutionManager): void {
        if (this.#soaiLinkResolution) throw new Error('Composer SoAI link resolution is already initialized');
        this.#soaiLinkResolution = manager;
    }

    initializeUi(manager: ChatUIManager): void {
        if (this.#ui) {
            manager.dispose();
            return;
        }
        this.#ui = manager;
    }

    initializeAttachments(manager: ChatAttachmentManager): void {
        if (this.#attachments) {
            manager.dispose();
            return;
        }
        this.#attachments = manager;
    }

    hasUi(): boolean {
        return this.#ui !== null;
    }

    hasAttachments(): boolean {
        return this.#attachments !== null;
    }

    optionalAttachments(): ChatAttachmentManager | null {
        return this.#attachments;
    }

    optionalUi(): ChatUIManager | null {
        return this.#ui;
    }

    requireUi(): ChatUIManager {
        if (!this.#ui) throw new Error('Chat UI manager is not initialized');
        return this.#ui;
    }

    requireAttachments(): ChatAttachmentManager {
        if (!this.#attachments) throw new Error('Chat attachment manager is not initialized');
        return this.#attachments;
    }

    requireSoaiLinkResolution(): ComposerSoaiLinkResolutionManager {
        if (!this.#soaiLinkResolution) throw new Error('Composer SoAI link resolution is not initialized');
        return this.#soaiLinkResolution;
    }

    dispose(): void {
        this.#attachments?.dispose();
        this.#attachments = null;
        this.#ui?.dispose();
        this.#ui = null;
        this.#soaiLinkResolution = null;
    }

    disposeAttachments(): void {
        this.#attachments?.dispose();
        this.#attachments = null;
    }

    disposeUi(): void {
        this.#ui?.dispose();
        this.#ui = null;
    }
}

export { ChatComposerSurfaceRuntime };
export interface ChatComposerSurfaceRuntimeOwner {
    composerSurface: ChatComposerSurfaceRuntime;
}
