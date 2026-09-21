/* SoAI - Frontend canonical WebSocket event contract registry [frontend/assets/ts/core/realtime/eventcontracts/registry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { AGENT_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/agentContracts.ts';
import { ATTACHMENT_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/attachmentContracts.ts';
import { AUTOMATION_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/automationContracts.ts';
import { CHAT_CONTROL_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/chatControlContracts.ts';
import { CHAT_STREAM_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/chatStreamContracts.ts';
import { CONVERSATION_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/conversationContracts.ts';
import { LIFECYCLE_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/lifecycleContracts.ts';
import { LICENSING_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/licensingContracts.ts';
import { MCP_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/mcpContracts.ts';
import { MODEL_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/modelContracts.ts';
import { NOTIFICATION_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/notificationContracts.ts';
import { PROVIDER_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/providerContracts.ts';
import { TASK_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/taskContracts.ts';
import { TERMINAL_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/terminalContracts.ts';
import { TOOL_LIVE_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/toolLiveContracts.ts';

const WEBSOCKET_EVENT_CONTRACTS = Object.freeze({
    agent: AGENT_EVENT_CONTRACTS,
    automation: AUTOMATION_EVENT_CONTRACTS,
    chat: CHAT_CONTROL_EVENT_CONTRACTS,
    attachment: ATTACHMENT_EVENT_CONTRACTS,
    chatStream: CHAT_STREAM_EVENT_CONTRACTS,
    conversation: CONVERSATION_EVENT_CONTRACTS,
    lifecycle: LIFECYCLE_EVENT_CONTRACTS,
    licensing: LICENSING_EVENT_CONTRACTS,
    terminal: TERMINAL_EVENT_CONTRACTS,
    mcp: MCP_EVENT_CONTRACTS,
    model: MODEL_EVENT_CONTRACTS,
    notification: NOTIFICATION_EVENT_CONTRACTS,
    provider: PROVIDER_EVENT_CONTRACTS,
    task: TASK_EVENT_CONTRACTS,
    toolLive: TOOL_LIVE_EVENT_CONTRACTS
});

const listWebSocketEventContracts = () =>
    Object.freeze([
        WEBSOCKET_EVENT_CONTRACTS.agent.turnStarted,
        WEBSOCKET_EVENT_CONTRACTS.agent.itemStarted,
        WEBSOCKET_EVENT_CONTRACTS.agent.itemDelta,
        WEBSOCKET_EVENT_CONTRACTS.agent.itemCompleted,
        WEBSOCKET_EVENT_CONTRACTS.agent.toolCallCreated,
        WEBSOCKET_EVENT_CONTRACTS.agent.toolCallStarted,
        WEBSOCKET_EVENT_CONTRACTS.agent.toolCallCompleted,
        WEBSOCKET_EVENT_CONTRACTS.agent.turnCompleted,
        WEBSOCKET_EVENT_CONTRACTS.agent.turnError,
        WEBSOCKET_EVENT_CONTRACTS.agent.todoUpdated,
        WEBSOCKET_EVENT_CONTRACTS.agent.planUpdated,
        WEBSOCKET_EVENT_CONTRACTS.agent.modeChanged,
        WEBSOCKET_EVENT_CONTRACTS.agent.subagentSpawned,
        WEBSOCKET_EVENT_CONTRACTS.agent.subagentRunning,
        WEBSOCKET_EVENT_CONTRACTS.agent.subagentCompleted,
        WEBSOCKET_EVENT_CONTRACTS.agent.subagentMaxIterations,
        WEBSOCKET_EVENT_CONTRACTS.agent.subagentError,
        WEBSOCKET_EVENT_CONTRACTS.agent.subagentAbandoned,
        WEBSOCKET_EVENT_CONTRACTS.agent.subagentCancelled,
        WEBSOCKET_EVENT_CONTRACTS.automation.created,
        WEBSOCKET_EVENT_CONTRACTS.automation.updated,
        WEBSOCKET_EVENT_CONTRACTS.automation.deleted,
        WEBSOCKET_EVENT_CONTRACTS.automation.runCreated,
        WEBSOCKET_EVENT_CONTRACTS.automation.runUpdated,
        WEBSOCKET_EVENT_CONTRACTS.chat.inputsChanged,
        WEBSOCKET_EVENT_CONTRACTS.chat.inputTerminal,
        WEBSOCKET_EVENT_CONTRACTS.chat.knowledgePromptChangedIdentity,
        WEBSOCKET_EVENT_CONTRACTS.chat.tokenCountResult,
        WEBSOCKET_EVENT_CONTRACTS.chat.tokenCountError,
        WEBSOCKET_EVENT_CONTRACTS.chat.draftChanged,
        WEBSOCKET_EVENT_CONTRACTS.attachment.conversationChanged,
        WEBSOCKET_EVENT_CONTRACTS.attachment.knowledgeChanged,
        WEBSOCKET_EVENT_CONTRACTS.chatStream.timeline,
        WEBSOCKET_EVENT_CONTRACTS.chatStream.commandError,
        WEBSOCKET_EVENT_CONTRACTS.chatStream.statusPreview,
        WEBSOCKET_EVENT_CONTRACTS.conversation.created,
        WEBSOCKET_EVENT_CONTRACTS.conversation.updated,
        WEBSOCKET_EVENT_CONTRACTS.conversation.deleted,
        WEBSOCKET_EVENT_CONTRACTS.conversation.messageSaved,
        WEBSOCKET_EVENT_CONTRACTS.lifecycle.connected,
        WEBSOCKET_EVENT_CONTRACTS.lifecycle.disconnected,
        WEBSOCKET_EVENT_CONTRACTS.licensing.statusChanged,
        WEBSOCKET_EVENT_CONTRACTS.terminal.connected,
        WEBSOCKET_EVENT_CONTRACTS.terminal.output,
        WEBSOCKET_EVENT_CONTRACTS.terminal.exited,
        WEBSOCKET_EVENT_CONTRACTS.terminal.disconnected,
        WEBSOCKET_EVENT_CONTRACTS.terminal.error,
        WEBSOCKET_EVENT_CONTRACTS.terminal.busy,
        WEBSOCKET_EVENT_CONTRACTS.mcp.notification,
        WEBSOCKET_EVENT_CONTRACTS.mcp.toolsChanged,
        WEBSOCKET_EVENT_CONTRACTS.mcp.resourcesChanged,
        WEBSOCKET_EVENT_CONTRACTS.mcp.promptsChanged,
        WEBSOCKET_EVENT_CONTRACTS.mcp.serverStarted,
        WEBSOCKET_EVENT_CONTRACTS.mcp.serverAdded,
        WEBSOCKET_EVENT_CONTRACTS.mcp.serverRemoved,
        WEBSOCKET_EVENT_CONTRACTS.mcp.serverConnected,
        WEBSOCKET_EVENT_CONTRACTS.mcp.serverDisconnected,
        WEBSOCKET_EVENT_CONTRACTS.mcp.toolInvoked,
        WEBSOCKET_EVENT_CONTRACTS.model.databaseChanged,
        WEBSOCKET_EVENT_CONTRACTS.notification.created,
        WEBSOCKET_EVENT_CONTRACTS.notification.markedRead,
        WEBSOCKET_EVENT_CONTRACTS.notification.deleted,
        WEBSOCKET_EVENT_CONTRACTS.provider.statusUpdated,
        WEBSOCKET_EVENT_CONTRACTS.task.created,
        WEBSOCKET_EVENT_CONTRACTS.task.complete,
        WEBSOCKET_EVENT_CONTRACTS.toolLive.updated
    ]);

export { WEBSOCKET_EVENT_CONTRACTS, listWebSocketEventContracts };
