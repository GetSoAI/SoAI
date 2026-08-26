/* SoAI - Frontend MCP WebSocket event contracts [frontend/assets/ts/core/realtime/eventcontracts/mcpContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { OpaqueJsonObject } from '@core/api/contracts/opaquePayload.ts';
import { defineWebSocketEventContract } from '@core/realtime/eventcontracts/contracts.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredFiniteNumberValue, readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { readRequiredBooleanValue, readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { WEBSOCKET_EVENT_TYPES } from '@core/websocketEvents.ts';

interface McpNotificationEvent extends McpBaseEvent {
    clientId: string;
    notification: OpaqueJsonObject;
}

interface McpBaseEvent {
    eventId: string;
    timestamp: number;
}
interface McpServerEvent extends McpBaseEvent {
    serverId: string;
    serverName?: string;
}
interface McpServerConnectedEvent extends McpServerEvent {
    serverName: string;
    toolsCount: number;
    resourcesCount: number;
}
interface McpServerDisconnectedEvent extends McpServerEvent {
    reason: string;
}
interface McpToolInvokedEvent extends McpServerEvent {
    toolName: string;
    success: boolean;
    executionTimeMs: number;
}

const decodeMcpBase = (payload: JsonValue): McpBaseEvent => {
    const record = requireRecord(payload, 'MCP event');
    const timestamp = readRequiredFiniteNumberValue(record['timestamp'], 'MCP event.timestamp');
    if (timestamp <= 0) throw new TypeError('MCP event.timestamp must be positive');
    return { eventId: readRequiredTrimmedStringValue(record['event_id'], 'MCP event.event_id'), timestamp };
};

const decodeMcpServer = (payload: JsonValue): McpServerEvent => {
    const record = requireRecord(payload, 'MCP server event');
    return { ...decodeMcpBase(payload), serverId: readRequiredTrimmedStringValue(record['server_id'], 'MCP server event.server_id') };
};

const decodeMcpServerNamed = (payload: JsonValue): McpServerEvent => {
    const record = requireRecord(payload, 'MCP server event');
    return { ...decodeMcpServer(payload), serverName: readRequiredTrimmedStringValue(record['server_name'], 'MCP server event.server_name') };
};

const decodeMcpServerConnected = (payload: JsonValue): McpServerConnectedEvent => {
    const record = requireRecord(payload, 'MCP connected event');
    return { ...decodeMcpServerNamed(payload), serverName: readRequiredTrimmedStringValue(record['server_name'], 'MCP connected event.server_name'), toolsCount: readRequiredNonNegativeIntegerValue(record['tools_count'], 'MCP connected event.tools_count'), resourcesCount: readRequiredNonNegativeIntegerValue(record['resources_count'], 'MCP connected event.resources_count') };
};

const decodeMcpToolInvoked = (payload: JsonValue): McpToolInvokedEvent => {
    const record = requireRecord(payload, 'MCP tool invoked event');
    const executionTimeMs = readRequiredFiniteNumberValue(record['execution_time_ms'], 'MCP tool invoked event.execution_time_ms');
    if (executionTimeMs < 0) throw new TypeError('MCP tool invoked event.execution_time_ms must be non-negative');
    return { ...decodeMcpServer(payload), toolName: readRequiredTrimmedStringValue(record['tool_name'], 'MCP tool invoked event.tool_name'), success: readRequiredBooleanValue(record['success'], 'MCP tool invoked event.success'), executionTimeMs };
};

const decodeMcpServerDisconnected = (payload: JsonValue): McpServerDisconnectedEvent => {
    const record = requireRecord(payload, 'MCP disconnected event');
    return { ...decodeMcpServer(payload), reason: readRequiredTrimmedStringValue(record['reason'], 'MCP disconnected event.reason') };
};

const decodeMcpNotification = (payload: JsonValue): McpNotificationEvent => {
    const record = requireRecord(payload, 'MCP notification event');
    return {
        ...decodeMcpBase(payload),
        clientId: readRequiredTrimmedStringValue(record['client_id'], 'MCP notification event.client_id'),
        notification: requireRecord(record['notification'], 'MCP notification event.notification')
    };
};

const MCP_EVENT_CONTRACTS = Object.freeze({
    notification: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.MCP_NOTIFICATION, decodeMcpNotification),
    toolsChanged: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.MCP_TOOLS_LIST_CHANGED, decodeMcpBase),
    resourcesChanged: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.MCP_RESOURCES_LIST_CHANGED, decodeMcpBase),
    promptsChanged: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.MCP_PROMPTS_LIST_CHANGED, decodeMcpBase),
    serverStarted: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.MCP_SERVER_STARTED, decodeMcpBase),
    serverAdded: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.MCP_SERVER_ADDED, decodeMcpServerNamed),
    serverRemoved: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.MCP_SERVER_REMOVED, decodeMcpServer),
    serverConnected: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.MCP_SERVER_CONNECTED, decodeMcpServerConnected),
    serverDisconnected: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.MCP_SERVER_DISCONNECTED, decodeMcpServerDisconnected),
    toolInvoked: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.MCP_TOOL_INVOKED, decodeMcpToolInvoked)
});

export { MCP_EVENT_CONTRACTS };
export type { McpNotificationEvent };
