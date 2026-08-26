/* SoAI - Chat page core effects [frontend/assets/ts/pages/chat/controllers/actionhandlers/core/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatConversationActionPort, ChatConversationActionsControllerContract, ChatExecutionActionPort } from '@pages/chat/controllers/actionhandlers/core/contracts.ts';

interface ChatActionEffectsHost {
    conversation: ChatConversationActionPort;
    execution: ChatExecutionActionPort;
}

const requireCurrentConversationId = (host: ChatActionEffectsHost): string => {
    const conversationId = host.conversation.currentId();
    if (!conversationId) {
        throw new Error('ChatPage requires a current conversation');
    }
    return conversationId;
};

const runConversationControllerAction = <ResultValue>(host: ChatActionEffectsHost, action: (controller: ChatConversationActionsControllerContract) => ResultValue): ResultValue => {
    return action(host.conversation.actions);
};

const collapseSidebarIfNarrowViewport = (host: ChatActionEffectsHost): void => {
    runConversationControllerAction(host, (controller) => controller.collapseSidebarIfNarrowViewport());
};

const isCurrentConversationExecuting = (host: ChatActionEffectsHost): boolean => {
    const conversationId = host.conversation.currentId();
    if (!conversationId) {
        return false;
    }
    return host.conversation.isExecuting(conversationId);
};

const isCurrentConversationChatStreaming = (host: ChatActionEffectsHost): boolean => {
    const conversationId = host.conversation.currentId();
    if (!conversationId) {
        return false;
    }
    return host.conversation.isStreaming(conversationId);
};

const runCollapsedUiTask = (host: ChatActionEffectsHost, operationId: string, task: () => Promise<void> | void): void => {
    collapseSidebarIfNarrowViewport(host);
    host.execution.run(operationId, task);
};

const runCollapsedAction = (host: ChatActionEffectsHost, action: () => void): void => {
    collapseSidebarIfNarrowViewport(host);
    action();
};

const createCollapsedActionHandler = (host: ChatActionEffectsHost, action: () => void): (() => void) => {
    return (): void => {
        runCollapsedAction(host, action);
    };
};

const createCollapsedActionHandlers = <ActionId extends string>(host: ChatActionEffectsHost, handlers: Record<ActionId, () => void>): Record<ActionId, () => void> => {
    const collapsedHandlers = { ...handlers };
    for (const actionId in handlers) {
        const handler = handlers[actionId];
        collapsedHandlers[actionId] = createCollapsedActionHandler(host, handler);
    }
    return collapsedHandlers;
};

const createCollapsedElementActionHandler = (host: ChatActionEffectsHost, action: (actionElement: HTMLElement) => void): ((actionElement: HTMLElement) => void) => {
    return (actionElement: HTMLElement): void => {
        runCollapsedAction(host, () => action(actionElement));
    };
};

const createEventPreludeActionHandler = (action: (actionElement: HTMLElement) => void, options: { preventDefault?: boolean; stopPropagation?: boolean }): ((actionElement: HTMLElement, event: Event) => void) => {
    return (actionElement: HTMLElement, event: Event): void => {
        if (options.preventDefault === true) {
            event.preventDefault();
        }
        if (options.stopPropagation === true) {
            event.stopPropagation();
        }
        action(actionElement);
    };
};

const withStoppedPropagation = (action: () => void): ((actionElement: HTMLElement, event: Event) => void) => {
    return createEventPreludeActionHandler(() => action(), { stopPropagation: true });
};

const createStoppedPropagationActionHandler = (action: (actionElement: HTMLElement) => void): ((actionElement: HTMLElement, event: Event) => void) => {
    return createEventPreludeActionHandler(action, { stopPropagation: true });
};

const createPreventDefaultStoppedActionHandler = (action: (actionElement: HTMLElement) => void): ((actionElement: HTMLElement, event: Event) => void) => {
    return createEventPreludeActionHandler(action, { preventDefault: true, stopPropagation: true });
};

const runConversationControllerUiTask = (host: ChatActionEffectsHost, operationId: string, action: (controller: ChatConversationActionsControllerContract) => Promise<void> | void): void => {
    host.execution.run(operationId, () => runConversationControllerAction(host, action));
};

const createMappedActionHandlers = <ActionId extends string>(handlers: Record<ActionId, () => void>): Record<ActionId, () => void> => {
    const mappedHandlers = { ...handlers };
    for (const actionId in handlers) {
        const handler = handlers[actionId];
        mappedHandlers[actionId] = (): void => {
            handler();
        };
    }
    return mappedHandlers;
};

export { collapseSidebarIfNarrowViewport, createCollapsedActionHandler, createCollapsedActionHandlers, createCollapsedElementActionHandler, createMappedActionHandlers, createPreventDefaultStoppedActionHandler, createStoppedPropagationActionHandler, isCurrentConversationChatStreaming, isCurrentConversationExecuting, requireCurrentConversationId, runCollapsedUiTask, runConversationControllerAction, runConversationControllerUiTask, withStoppedPropagation };
