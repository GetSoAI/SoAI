/* SoAI - MCP conversation settings events [frontend/assets/ts/features/chat/conversationsettings/mcpconversationsettingscontroller/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { bindDataActionListener, type DataActionEventType } from '@core/dom/dataActionBinding.ts';
import { MCP_CONVERSATION_ACTION_AUTO_TOGGLE, MCP_CONVERSATION_ACTION_DEFAULT_TOOL_TOGGLE, MCP_CONVERSATION_ACTION_OPEN_DEFAULT_TOOLS, MCP_CONVERSATION_ACTION_RESET_TOOL_MODE_DEFAULTS, MCP_CONVERSATION_ACTION_SERVER_TOGGLE, MCP_CONVERSATION_ACTION_TOOL_GROUP_TOGGLE, MCP_CONVERSATION_ACTION_TOOL_MODE_SELECT, MCP_CONVERSATION_ACTION_TOOL_SEARCH, MCP_CONVERSATION_ACTION_TOOL_TOGGLE, isMcpConversationChangeActionId, isMcpConversationClickActionId, isMcpConversationInputActionId, type McpConversationActionId } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/actionIds.ts';

interface McpConversationSettingsEventHandlers {
    onAutoToggleChange(toggleElement: HTMLElement): void;
    onServerToggleChange(toggleElement: HTMLElement): void;
    onToolToggleChange(toggleElement: HTMLElement): void;
    onToolModeTabClick(tabElement: HTMLElement): void;
    onToolGroupToggleClick(toggleElement: HTMLElement): void;
    onDefaultToolsTriggerClick(): void;
    onDefaultToolsToggleChange(toggleElement: HTMLElement): void;
    onToolModeResetClick(): void;
    onToolSearchInput(inputElement: HTMLElement): void;
}

interface BindMcpConversationSettingsEventsOptions {
    signal: AbortSignal;
    modal: HTMLElement;
    defaultToolsModal: HTMLElement;
    handlers: McpConversationSettingsEventHandlers;
}

type McpConversationActionGuard<TAction extends McpConversationActionId> = (value: Parameters<typeof isMcpConversationChangeActionId>[0]) => value is TAction;

const handleMcpConversationAction = (action: McpConversationActionId, actionElement: HTMLElement, handlers: McpConversationSettingsEventHandlers): void => {
    if (action === MCP_CONVERSATION_ACTION_AUTO_TOGGLE) {
        handlers.onAutoToggleChange(actionElement);
        return;
    }
    if (action === MCP_CONVERSATION_ACTION_SERVER_TOGGLE) {
        handlers.onServerToggleChange(actionElement);
        return;
    }
    if (action === MCP_CONVERSATION_ACTION_TOOL_TOGGLE) {
        handlers.onToolToggleChange(actionElement);
        return;
    }
    if (action === MCP_CONVERSATION_ACTION_TOOL_MODE_SELECT) {
        handlers.onToolModeTabClick(actionElement);
        return;
    }
    if (action === MCP_CONVERSATION_ACTION_TOOL_GROUP_TOGGLE) {
        handlers.onToolGroupToggleClick(actionElement);
        return;
    }
    if (action === MCP_CONVERSATION_ACTION_OPEN_DEFAULT_TOOLS) {
        handlers.onDefaultToolsTriggerClick();
        return;
    }
    if (action === MCP_CONVERSATION_ACTION_DEFAULT_TOOL_TOGGLE) {
        handlers.onDefaultToolsToggleChange(actionElement);
        return;
    }
    if (action === MCP_CONVERSATION_ACTION_RESET_TOOL_MODE_DEFAULTS) {
        handlers.onToolModeResetClick();
        return;
    }
    if (action === MCP_CONVERSATION_ACTION_TOOL_SEARCH) {
        handlers.onToolSearchInput(actionElement);
        return;
    }
    throw new Error('Unknown MCP conversation settings action');
};

const bindMcpConversationSettingsEvents = ({ signal, modal, defaultToolsModal, handlers }: BindMcpConversationSettingsEventsOptions): void => {
    const bindActionRoot = <TAction extends McpConversationActionId>(root: HTMLElement, eventType: DataActionEventType, isAction: McpConversationActionGuard<TAction>): void => {
        bindDataActionListener({
            root,
            eventType,
            signal,
            isAction,
            preventDefault: 'never',
            ignoreDisabled: true,
            onAction: ({ action, actionElement }): void => handleMcpConversationAction(action, actionElement, handlers)
        });
    };
    for (const root of [modal, defaultToolsModal]) {
        bindActionRoot(root, 'change', isMcpConversationChangeActionId);
        bindActionRoot(root, 'click', isMcpConversationClickActionId);
        bindActionRoot(root, 'input', isMcpConversationInputActionId);
    }
};

export { bindMcpConversationSettingsEvents };
export type { BindMcpConversationSettingsEventsOptions, McpConversationSettingsEventHandlers };
