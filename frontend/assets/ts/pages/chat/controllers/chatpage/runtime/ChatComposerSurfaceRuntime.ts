/* SoAI - Chat composer UI and attachment lifecycle ownership [frontend/assets/ts/pages/chat/controllers/chatpage/runtime/ChatComposerSurfaceRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AttachModalController } from '@features/attachmodal/public.ts';
import type { ChatAttachmentManager, ChatUIManager } from '@features/chat/public.ts';
import type { ComposerSoaiLinkResolutionManager } from '@pages/chat/controllers/chatmessagesendingcontroller/composerSoaiLinkResolutionManager.ts';

class ChatComposerSurfaceRuntime {
    #attachModal: AttachModalController | null = null;
    #ui: ChatUIManager | null = null;
    #attachments: ChatAttachmentManager | null = null;
    #soaiLinkResolution: ComposerSoaiLinkResolutionManager | null = null;

    initializeAttachModal(controller: AttachModalController): void {
        if (this.#attachModal !== null) throw new Error('Attachment dialog is already initialized');
        this.#attachModal = controller;
    }

    requireAttachModal(): AttachModalController {
        if (this.#attachModal === null) throw new Error('Attachment dialog is not initialized');
        return this.#attachModal;
    }

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
        this.#attachModal?.disposeForPageDestroy();
        this.#attachModal = null;
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
