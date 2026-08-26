/* SoAI - Chat controller initialization ownership [frontend/assets/ts/pages/chat/controllers/chatpage/runtime/ChatControllerInitialization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { AsyncOnceGuard } from '@core/concurrency/AsyncOnce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { ChatMessageSendingPort } from '@pages/chat/controllers/chatmessagesendingcontroller/types.ts';
import type { ChatActionId } from '@features/chat/public.ts';
import type { ChatPageActionRuntime } from '@pages/chat/controllers/chatpage/construction/createActionHandlers.ts';
import type { ChatActionHandlersHost } from '@pages/chat/controllers/actionhandlers/core/contracts.ts';

type ChatRootActionHandler = (actionElement: HTMLElement, event: Event) => void;
type ChatRootActionHandlerMap = Record<ChatActionId, ChatRootActionHandler>;

interface ChatControllerInitializationDependencies {
    initializeManagers(messageSending: ChatMessageSendingPort): void;
    initializeConversationActions(): void;
    initializeActionHandlers(messageSending: ChatMessageSendingPort): ChatPageActionRuntime;
    initializeVoiceCall(messageSending: ChatMessageSendingPort): Promise<void>;
    ensureToolIconsLoaded(): Promise<void>;
    initializeAgent(): void;
    updateAgentUi(): void;
}

const loadChatToolIconsForInitialization = async (load: () => Promise<void>): Promise<void> => {
    try {
        await load();
    } catch (error) {
        errorHandler.warn('ChatPage', 'Chat tool icons failed to load', ensureError(error));
    }
};

class ChatControllerInitialization {
    readonly #dependencies: ChatControllerInitializationDependencies;
    readonly #once = new AsyncOnceGuard<void>();
    #actionHandlers: ChatRootActionHandlerMap | null = null;
    #actionHost: ChatActionHandlersHost | null = null;

    constructor(dependencies: ChatControllerInitializationDependencies) {
        this.#dependencies = dependencies;
    }

    async ensureInitialized(messageSending: ChatMessageSendingPort): Promise<void> {
        await this.#once.run(async () => {
            const dependencies = this.#dependencies;
            dependencies.initializeManagers(messageSending);
            dependencies.initializeConversationActions();
            const actionRuntime = dependencies.initializeActionHandlers(messageSending);
            this.#actionHandlers = actionRuntime.handlers;
            this.#actionHost = actionRuntime.host;
            await dependencies.initializeVoiceCall(messageSending);
            await loadChatToolIconsForInitialization(dependencies.ensureToolIconsLoaded);
            dependencies.initializeAgent();
            dependencies.updateAgentUi();
        });
    }

    dispatch(action: ChatActionId, actionElement: HTMLElement, event: Event): void {
        const handlers = this.#actionHandlers;
        if (handlers === null) throw new Error('Chat controller actions are not initialized');
        const handler = handlers[action];
        if (typeof handler !== 'function') throw new Error(`Chat root action is not registered: ${action}`);
        handler(actionElement, event);
    }

    requireActionHost(): ChatActionHandlersHost {
        if (this.#actionHost === null) throw new Error('Chat controller actions are not initialized');
        return this.#actionHost;
    }

    dispose(): void {
        this.#actionHandlers = null;
        this.#actionHost = null;
    }
}

export { ChatControllerInitialization, loadChatToolIconsForInitialization };
export type { ChatControllerInitializationDependencies, ChatRootActionHandler, ChatRootActionHandlerMap };
