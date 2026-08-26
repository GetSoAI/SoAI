/* SoAI - Chat page agent action handlers [frontend/assets/ts/pages/chat/controllers/actionhandlers/core/agentActionHandlers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { beginLoadingButtonWithClear } from '@core/ui/loadingbuttons/service.ts';
import { CHAT_ACTIONS } from '@features/chat/public.ts';
import { createMappedActionHandlers } from '@pages/chat/controllers/actionhandlers/core/effects.ts';
import type { ChatActionHandler, ChatAgentActionPort, ChatComposerActionPort, ChatExecutionActionPort, ChatPresentationActionPort, ChatToolbarActionPort } from '@pages/chat/controllers/actionhandlers/core/contracts.ts';

interface ChatAgentActionsHost {
    agent: ChatAgentActionPort;
    composer: ChatComposerActionPort;
    execution: ChatExecutionActionPort;
    presentation: ChatPresentationActionPort;
    toolbar: ChatToolbarActionPort;
}

type ChatAgentActionId = typeof CHAT_ACTIONS.CYCLE_AGENT_MODE | typeof CHAT_ACTIONS.COMPACT_AGENT | typeof CHAT_ACTIONS.TOGGLE_TOOLS | typeof CHAT_ACTIONS.TOGGLE_TODO_PANEL | typeof CHAT_ACTIONS.TOGGLE_PLAN_BAR | typeof CHAT_ACTIONS.VIEW_AGENT_PLAN | typeof CHAT_ACTIONS.EXECUTE_AGENT_PLAN | typeof CHAT_ACTIONS.TOGGLE_TOOLBAR | typeof CHAT_ACTIONS.ENTER_SELECT_MODE | typeof CHAT_ACTIONS.EXIT_SELECT_MODE | typeof CHAT_ACTIONS.BATCH_DELETE | typeof CHAT_ACTIONS.BATCH_ARCHIVE | typeof CHAT_ACTIONS.BATCH_CLONE | typeof CHAT_ACTIONS.OPEN_ARCHIVED_CONVERSATIONS | typeof CHAT_ACTIONS.UPLOAD_USER_AVATAR | typeof CHAT_ACTIONS.REMOVE_USER_AVATAR | typeof CHAT_ACTIONS.UPLOAD_ASSISTANT_AVATAR | typeof CHAT_ACTIONS.REMOVE_ASSISTANT_AVATAR;
type ChatLoadingAgentActionId = typeof CHAT_ACTIONS.TOGGLE_TOOLS | typeof CHAT_ACTIONS.EXECUTE_AGENT_PLAN | typeof CHAT_ACTIONS.BATCH_DELETE | typeof CHAT_ACTIONS.BATCH_ARCHIVE | typeof CHAT_ACTIONS.BATCH_CLONE;
type ChatMappedAgentActionId = Exclude<ChatAgentActionId, ChatLoadingAgentActionId>;

const runLoadingButtonAction = (host: ChatAgentActionsHost, actionElement: HTMLElement, operationId: string, action: () => Promise<void>, afterClear?: () => void): void => {
    const clearLoading = actionElement instanceof HTMLButtonElement ? beginLoadingButtonWithClear(actionElement) : null;
    host.execution.run(operationId, async () => {
        try {
            await action();
        } finally {
            clearLoading?.();
            afterClear?.();
        }
    });
};

const createChatAgentActionHandlers = (host: ChatAgentActionsHost): Record<ChatAgentActionId, ChatActionHandler> => {
    const mappedHandlers = createMappedActionHandlers<ChatMappedAgentActionId>({
        [CHAT_ACTIONS.CYCLE_AGENT_MODE]: () => host.agent.cycleMode(),
        [CHAT_ACTIONS.COMPACT_AGENT]: () => host.agent.compact(),
        [CHAT_ACTIONS.TOGGLE_TODO_PANEL]: () => host.agent.toggleTodoPanel(),
        [CHAT_ACTIONS.TOGGLE_PLAN_BAR]: () => host.agent.togglePlanBar(),
        [CHAT_ACTIONS.VIEW_AGENT_PLAN]: () => host.agent.viewPlan(),
        [CHAT_ACTIONS.TOGGLE_TOOLBAR]: () => host.toolbar.toggle(),
        [CHAT_ACTIONS.ENTER_SELECT_MODE]: () => host.toolbar.enterSelectMode(),
        [CHAT_ACTIONS.EXIT_SELECT_MODE]: () => host.toolbar.exitSelectMode(),
        [CHAT_ACTIONS.OPEN_ARCHIVED_CONVERSATIONS]: () => host.toolbar.openArchived(),
        [CHAT_ACTIONS.UPLOAD_USER_AVATAR]: () => host.presentation.uploadUserAvatar(),
        [CHAT_ACTIONS.REMOVE_USER_AVATAR]: () => host.presentation.removeUserAvatar(),
        [CHAT_ACTIONS.UPLOAD_ASSISTANT_AVATAR]: () => host.presentation.uploadAssistantAvatar(),
        [CHAT_ACTIONS.REMOVE_ASSISTANT_AVATAR]: () => host.presentation.removeAssistantAvatar()
    });
    return {
        ...mappedHandlers,
        [CHAT_ACTIONS.TOGGLE_TOOLS]: (actionElement) =>
            runLoadingButtonAction(
                host,
                actionElement,
                'chat:toggleTools',
                () => host.composer.toggleTools(),
                () => host.composer.applyInputActionVisibility()
            ),
        [CHAT_ACTIONS.EXECUTE_AGENT_PLAN]: (actionElement) => runLoadingButtonAction(host, actionElement, 'chat:executeAgentPlan', () => host.agent.executePlan()),
        [CHAT_ACTIONS.BATCH_DELETE]: (actionElement) => runLoadingButtonAction(host, actionElement, 'chat:batchOperation', () => host.toolbar.deleteSelected()),
        [CHAT_ACTIONS.BATCH_ARCHIVE]: (actionElement) => runLoadingButtonAction(host, actionElement, 'chat:batchOperation', () => host.toolbar.archiveSelected()),
        [CHAT_ACTIONS.BATCH_CLONE]: (actionElement) => runLoadingButtonAction(host, actionElement, 'chat:batchOperation', () => host.toolbar.cloneSelected())
    };
};

export { createChatAgentActionHandlers };
