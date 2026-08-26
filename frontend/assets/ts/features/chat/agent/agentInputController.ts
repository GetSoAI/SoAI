/* SoAI - Chat feature agent input controller [frontend/assets/ts/features/chat/agent/agentInputController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface AgentInputControllerDependencies {
    getChatInput(): HTMLTextAreaElement | null;
    cycleMode(): void;
}

interface AgentInputController {
    handleKeyDown(event: KeyboardEvent): boolean;
}

const isChatInputTarget = (event: KeyboardEvent, input: HTMLTextAreaElement | null): boolean => {
    if (!input) {
        return false;
    }
    return event.target === input;
};

const createAgentInputController = (dependencies: AgentInputControllerDependencies): AgentInputController => {
    const handleKeyDown = (event: KeyboardEvent): boolean => {
        const input = dependencies.getChatInput();
        if (!isChatInputTarget(event, input)) {
            return false;
        }

        if (event.key === 'Tab' && event.shiftKey && !event.ctrlKey && !event.metaKey && !event.altKey) {
            event.preventDefault();
            dependencies.cycleMode();
            return true;
        }

        return false;
    };

    return { handleKeyDown };
};

export { createAgentInputController };
export type { AgentInputController, AgentInputControllerDependencies };
