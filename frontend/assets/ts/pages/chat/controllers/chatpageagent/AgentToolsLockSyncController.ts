/* SoAI - Chat page agent tools lock synchronization controller [frontend/assets/ts/pages/chat/controllers/chatpageagent/AgentToolsLockSyncController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface AgentToolsLockSyncHost {
    conversation: {
        getCurrentConversationId(): string | null;
    };
    interaction: {
        handleCurrentConversationToolsLockStateChange(): void;
        updateInputState(): void;
        updateParameterUI(): void;
    };
}

interface AgentToolsLockSyncControllerArguments {
    host: AgentToolsLockSyncHost;
    isRenderingActive(conversationId: string): boolean;
}

class AgentToolsLockSyncController {
    #host: AgentToolsLockSyncHost;
    #isRenderingActive: (conversationId: string) => boolean;
    #lastConversationId: string | null = null;
    #lastActive: boolean | null = null;

    constructor(inputArguments: AgentToolsLockSyncControllerArguments) {
        this.#host = inputArguments.host;
        this.#isRenderingActive = inputArguments.isRenderingActive;
    }

    sync(): void {
        const conversationId = this.#host.conversation.getCurrentConversationId();
        const active = conversationId ? this.#isRenderingActive(conversationId) : false;
        if (this.#lastConversationId === conversationId && this.#lastActive === active) {
            return;
        }
        this.#lastConversationId = conversationId;
        this.#lastActive = active;
        this.#host.interaction.handleCurrentConversationToolsLockStateChange();
        this.#host.interaction.updateInputState();
        this.#host.interaction.updateParameterUI();
    }

    clear(): void {
        this.#lastConversationId = null;
        this.#lastActive = null;
    }
}

export { AgentToolsLockSyncController };
export type { AgentToolsLockSyncHost };
