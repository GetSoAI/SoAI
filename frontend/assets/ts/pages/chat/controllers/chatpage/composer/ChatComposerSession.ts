/* SoAI - Chat composer token-counter, elicitation, and draft session ownership [frontend/assets/ts/pages/chat/controllers/chatpage/composer/ChatComposerSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { ChatComposerDraftManager, ChatElicitationSession, ComposerDraftFlushOptions } from '@features/chat/public.ts';
import { resolveTokenCounterControllerForPage } from '@pages/chat/controllers/chatpage/construction/resolveTokenCounterController.ts';
import type { ChatTokenCounterController } from '@pages/chat/widgets/tokencounter/ChatTokenCounterController.ts';

class ChatComposerSession {
    readonly #pageDom: PageDom;
    #tokenCounter: ChatTokenCounterController | null = null;
    #elicitation: ChatElicitationSession | null = null;
    #draft: ChatComposerDraftManager | null = null;

    constructor(pageDom: PageDom) {
        this.#pageDom = pageDom;
    }

    initializeTokenCounter(controller: ChatTokenCounterController): void {
        if (this.#tokenCounter) {
            controller.dispose();
            return;
        }
        this.#tokenCounter = controller;
        controller.initialize();
    }

    get hasTokenCounter(): boolean {
        return this.#tokenCounter !== null;
    }

    cycleTokenCounter(): void {
        if (!this.#tokenCounter) throw new Error('Chat token counter controller is not initialized');
        this.#tokenCounter.cycleMode();
    }

    disposeTokenCounter(): void {
        this.#tokenCounter?.dispose();
        this.#tokenCounter = null;
    }

    withTokenCounter(operation: (controller: ChatTokenCounterController) => void): void {
        const controller = resolveTokenCounterControllerForPage({
            pageDom: this.#pageDom,
            getTokenCounterController: () => this.#tokenCounter,
            setTokenCounterController: (nextController) => {
                this.#tokenCounter = nextController;
            }
        });
        if (controller) operation(controller);
    }

    initializeElicitation(session: ChatElicitationSession): void {
        if (this.#elicitation) {
            session.dispose();
            return;
        }
        this.#elicitation = session;
    }

    get hasElicitation(): boolean {
        return this.#elicitation !== null;
    }

    requireElicitation(): ChatElicitationSession {
        if (!this.#elicitation) throw new Error('Chat elicitation session is not initialized');
        return this.#elicitation;
    }

    handleConversationRendered(conversationId: string | null): void {
        this.#elicitation?.handleConversationRendered(conversationId);
    }

    disposeElicitation(): void {
        this.#elicitation?.dispose();
        this.#elicitation = null;
    }

    initializeDraft(manager: ChatComposerDraftManager): void {
        if (this.#draft) {
            manager.dispose();
            return;
        }
        this.#draft = manager;
        manager.ensureInitialized();
    }

    get draft(): ChatComposerDraftManager | null {
        return this.#draft;
    }

    async flushDraft(reason: string, options: ComposerDraftFlushOptions = {}): Promise<void> {
        if (!this.#draft) throw new Error('Chat composer draft manager is not initialized');
        await this.#draft.flushNow(reason, options);
    }

    disposeDraft(): void {
        this.#draft?.dispose();
        this.#draft = null;
    }
}

export { ChatComposerSession };
