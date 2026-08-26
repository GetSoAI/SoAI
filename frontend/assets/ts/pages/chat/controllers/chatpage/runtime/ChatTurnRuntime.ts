/* SoAI - Chat streaming, conversation input, and agent turn ownership [frontend/assets/ts/pages/chat/controllers/chatpage/runtime/ChatTurnRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatConversationInputsManager, ChatStreamingController } from '@features/chat/public.ts';
import type { ChatPageAgentService } from '@pages/chat/controllers/chatpageagent/contracts.ts';

class ChatTurnRuntime {
    #streaming: ChatStreamingController | null = null;
    #conversationInputs: ChatConversationInputsManager | null = null;
    #agent: ChatPageAgentService | null = null;

    initializeStreaming(controller: ChatStreamingController): void {
        if (this.#streaming) {
            controller.dispose();
            return;
        }
        this.#streaming = controller;
    }

    initializeConversationInputs(manager: ChatConversationInputsManager): void {
        if (this.#conversationInputs) {
            manager.dispose();
            return;
        }
        this.#conversationInputs = manager;
    }

    initializeAgent(service: ChatPageAgentService): void {
        if (this.#agent) {
            service.dispose();
            return;
        }
        this.#agent = service;
    }

    hasStreaming(): boolean {
        return this.#streaming !== null;
    }

    hasConversationInputs(): boolean {
        return this.#conversationInputs !== null;
    }

    optionalConversationInputs(): ChatConversationInputsManager | null {
        return this.#conversationInputs;
    }

    optionalAgent(): ChatPageAgentService | null {
        return this.#agent;
    }

    requireStreaming(): ChatStreamingController {
        if (!this.#streaming) throw new Error('Chat streaming controller is not initialized');
        return this.#streaming;
    }

    requireConversationInputs(): ChatConversationInputsManager {
        if (!this.#conversationInputs) throw new Error('Chat conversation inputs manager is not initialized');
        return this.#conversationInputs;
    }

    requireAgent(): ChatPageAgentService {
        if (!this.#agent) throw new Error('Chat agent service is not initialized');
        return this.#agent;
    }

    dispose(): void {
        this.#streaming?.dispose();
        this.#streaming = null;
        this.#conversationInputs?.dispose();
        this.#conversationInputs = null;
        this.#agent?.dispose();
        this.#agent = null;
    }

    disposeStreamingAndConversationInputs(): void {
        this.#streaming?.dispose();
        this.#streaming = null;
        this.#conversationInputs?.dispose();
        this.#conversationInputs = null;
    }

    disposeAgent(): void {
        this.#agent?.dispose();
        this.#agent = null;
    }
}

export { ChatTurnRuntime };
export interface ChatTurnRuntimeOwner {
    turnRuntime: ChatTurnRuntime;
}
