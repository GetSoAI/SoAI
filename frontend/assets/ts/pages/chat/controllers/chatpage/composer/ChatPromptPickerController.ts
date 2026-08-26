/* SoAI - Chat prompt picker and composer insertion ownership [frontend/assets/ts/pages/chat/controllers/chatpage/composer/ChatPromptPickerController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ChatPromptsPickerModalController } from '@pages/chat/controllers/modals/promptspicker/ChatPromptsPickerModalController.ts';
import type { ChatPromptsPickerStreamManager } from '@pages/chat/controllers/modals/promptspicker/types.ts';
import type { ChatPageApi } from '@features/chat/public.ts';
import type { ChatComposerHost } from '@pages/chat/controllers/chatpage/composer/ChatComposerController.ts';
import type { ChatUiTaskScopeHost } from '@pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts';
import type { ChatPagePresentationHost } from '@pages/chat/controllers/chatpage/presentation/contracts.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';

interface ChatPromptPickerPage extends ChatComposerHost, ChatUiTaskScopeHost, ChatPagePresentationHost, PageFeedbackOwnerHost {
    api: ChatPageApi;
    getDocument(): Document;
    requireStreamManager(): ChatPromptsPickerStreamManager;
    navigate(page: string): void | Promise<void>;
}

class ChatPromptPickerController {
    readonly #page: ChatPromptPickerPage;
    #controller: ChatPromptsPickerModalController | null = null;

    constructor(page: ChatPromptPickerPage) {
        this.#page = page;
    }

    open(): void {
        this.#page.taskScope.run('chat:openPromptsPicker', async () => {
            this.#controller?.dispose();
            this.#controller = new ChatPromptsPickerModalController({
                feedback: this.#page.feedback,
                api: this.#page.api,
                getDocument: () => this.#page.getDocument(),
                getCachedIcon: (name, options) => this.#page.presentation.cachedIcon(name, options),
                requireStreamManager: () => this.#page.requireStreamManager(),
                insertPromptContentIntoComposer: (content) => this.insertPromptContent(content),
                navigate: (page) => this.#page.navigate(page)
            });
            await this.#controller.open();
        });
    }

    dispose(): void {
        this.#controller?.dispose();
        this.#controller = null;
    }

    insertPromptContent(content: string): void {
        this.#page.composer.insertTextAtCaret(content, 'block');
    }
}

export { ChatPromptPickerController };
export type { ChatPromptPickerPage };
