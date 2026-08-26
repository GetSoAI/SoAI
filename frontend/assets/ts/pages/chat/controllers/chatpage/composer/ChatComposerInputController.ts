/* SoAI - Chat composer input mutation, sizing, hint, and task ownership [frontend/assets/ts/pages/chat/controllers/chatpage/composer/ChatComposerInputController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageUi } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { ChatComposerSurfaceRuntime } from '@pages/chat/controllers/chatpage/runtime/ChatComposerSurfaceRuntime.ts';
import type { ChatPageElementsManager } from '@pages/chat/controllers/chatpage/presentation/ChatPageElementsManager.ts';
import type { ChatUiTaskScopeContract } from '@pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts';
import { updateEmptyStateInputHint } from '@pages/chat/controllers/page/dom/emptyState.ts';

class ChatComposerInputController {
    readonly #composerSurface: ChatComposerSurfaceRuntime;
    readonly #elements: ChatPageElementsManager;
    readonly #pageDom: PageDom;
    readonly #pageElements: PageUi;
    readonly #resize: (textarea: Element) => void;
    readonly #taskScope: ChatUiTaskScopeContract;

    constructor(dependencies: { composerSurface: ChatComposerSurfaceRuntime; elements: ChatPageElementsManager; pageDom: PageDom; pageElements: PageUi; resize: (textarea: Element) => void; taskScope: ChatUiTaskScopeContract }) {
        this.#composerSurface = dependencies.composerSurface;
        this.#elements = dependencies.elements;
        this.#pageDom = dependencies.pageDom;
        this.#pageElements = dependencies.pageElements;
        this.#resize = dependencies.resize;
        this.#taskScope = dependencies.taskScope;
    }

    getChatInput(): HTMLTextAreaElement | null {
        return this.#elements.getChatInputElement();
    }

    setUIValue(element: Element, value: string, options?: { attribute?: string }): void {
        this.#pageElements.setValue(element, value, options);
    }

    resizeChatInput(textarea: Element): void {
        this.#resize(textarea);
    }

    updateInputState(): void {
        this.#composerSurface.requireUi().updateInputState();
    }

    updateEmptyStateInputHint(): void {
        updateEmptyStateInputHint({ pageDom: this.#pageDom }, this.#elements.getChatInputElement(), this.#composerSurface.optionalAttachments());
    }

    runUiTask(operationId: string, task: () => Promise<void> | void): void {
        this.#taskScope.run(operationId, task);
    }
}

export { ChatComposerInputController };
