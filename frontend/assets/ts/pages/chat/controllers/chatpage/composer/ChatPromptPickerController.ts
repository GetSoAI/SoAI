/* SoAI - Chat prompt picker and composer insertion ownership [frontend/assets/ts/pages/chat/controllers/chatpage/composer/ChatPromptPickerController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { PromptsPickerModalController, type PromptsPickerStreamManager } from '@features/prompts/public.ts';
import { windowIdentity } from '@core/runtime/windowIdentity.ts';
import type { ChatPageApi } from '@features/chat/public.ts';
import type { ChatComposerHost } from '@pages/chat/controllers/chatpage/composer/ChatComposerController.ts';
import type { ChatUiTaskScopeHost } from '@pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts';
import type { ChatPagePresentationHost } from '@pages/chat/controllers/chatpage/presentation/contracts.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';

interface ChatPromptPickerPage extends ChatComposerHost, ChatUiTaskScopeHost, ChatPagePresentationHost, PageFeedbackOwnerHost {
    api: ChatPageApi;
    getDocument(): Document;
    requireStreamManager(): PromptsPickerStreamManager;
    navigate(page: string): void | Promise<void>;
}

class ChatPromptPickerController {
    readonly #page: ChatPromptPickerPage;
    #controller: PromptsPickerModalController | null = null;

    constructor(page: ChatPromptPickerPage) {
        this.#page = page;
    }

    open(): void {
        this.#page.taskScope.run('chat:openPromptsPicker', async () => {
            this.#controller?.dispose();
            this.#controller = new PromptsPickerModalController({
                feedback: this.#page.feedback,
                promptsApi: this.#page.api.webui.prompts,
                getDocument: () => this.#page.getDocument(),
                getCachedIcon: (name, options) => this.#page.presentation.cachedIcon(name, options),
                requireStreamManager: () => this.#page.requireStreamManager(),
                onSelect: (content) => this.insertPromptContent(content),
                openLibrary: windowIdentity.isDetachedContext() ? null : () => this.#page.navigate('prompts')
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
