/* SoAI - Chat parameter and conversation configuration lifecycle ownership [frontend/assets/ts/pages/chat/controllers/chatpage/runtime/ChatConfigurationRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatConversationSettingsManager, ChatParameterManager } from '@features/chat/public.ts';
import type { ChatConfigurationController } from '@pages/chat/controllers/chatconfigurationcontroller/ChatConfigurationController.ts';

class ChatConfigurationRuntime {
    #parameters: ChatParameterManager | null = null;
    #conversationSettings: ChatConversationSettingsManager | null = null;
    #configuration: ChatConfigurationController | null = null;

    initializeParameters(manager: ChatParameterManager): void {
        if (this.#parameters) throw new Error('Chat parameter manager is already initialized');
        this.#parameters = manager;
    }

    initializeConversationSettings(manager: ChatConversationSettingsManager): void {
        if (this.#conversationSettings) {
            manager.dispose();
            return;
        }
        this.#conversationSettings = manager;
    }

    initializeConfiguration(controller: ChatConfigurationController): void {
        if (this.#configuration) {
            controller.dispose();
            return;
        }
        this.#configuration = controller;
    }

    hasParameters(): boolean {
        return this.#parameters !== null;
    }

    hasConversationSettings(): boolean {
        return this.#conversationSettings !== null;
    }

    optionalParameters(): ChatParameterManager | null {
        return this.#parameters;
    }

    optionalConversationSettings(): ChatConversationSettingsManager | null {
        return this.#conversationSettings;
    }

    optionalConfiguration(): ChatConfigurationController | null {
        return this.#configuration;
    }

    requireParameters(): ChatParameterManager {
        if (!this.#parameters) throw new Error('Chat parameter manager is not initialized');
        return this.#parameters;
    }

    requireConversationSettings(): ChatConversationSettingsManager {
        if (!this.#conversationSettings) throw new Error('Chat conversation settings manager is not initialized');
        return this.#conversationSettings;
    }

    requireConfiguration(): ChatConfigurationController {
        if (!this.#configuration) throw new Error('Chat configuration controller is not initialized');
        return this.#configuration;
    }

    dispose(): void {
        this.#configuration?.dispose();
        this.#configuration = null;
        this.#conversationSettings?.dispose();
        this.#conversationSettings = null;
        this.#parameters = null;
    }

    disposeConversationSettings(): void {
        this.#conversationSettings?.dispose();
        this.#conversationSettings = null;
    }
}

export { ChatConfigurationRuntime };
export interface ChatConfigurationRuntimeOwner {
    configurationRuntime: ChatConfigurationRuntime;
}
