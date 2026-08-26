/* SoAI - Frontend chat agent subagent domain types [frontend/assets/ts/core/chat/agentSubagentTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';

type AgentSubagentStatus = 'accepted' | 'running' | 'completed' | 'error' | 'cancelled' | 'max_iterations' | 'abandoned';

type AgentSubagentSnapshot = {
    subagentId: string;
    executionType: string;
    ownerTaskId: string | null;
    status: Exclude<AgentSubagentStatus, 'accepted'>;
    statusMessage: string | null;
    mode: 'plan' | 'execute';
    displayName: string | null;
    parentTurnId: string;
    parentToolCallId: string;
    parentIterationIndex: number;
    startedAtMs: number;
    updatedAtMs: number;
    finishedAtMs: number | null;
    requestedModel: string | null;
    resultText: string | null;
    errorMessage: string | null;
    errorType: string | null;
    tokenUsage: JsonObject | null;
};

type AgentSubagentState = {
    subagentId: string;
    executionType: string;
    ownerTaskId: string | null;
    status: AgentSubagentStatus;
    statusMessage: string | null;
    mode: 'plan' | 'execute';
    displayName: string | null;
    parentTurnId: string;
    parentToolCallId: string;
    parentIterationIndex: number;
    startedAtMs: number;
    updatedAtMs: number;
    finishedAtMs: number | null;
    requestedModel: string | null;
    resultText: string | null;
    errorMessage: string | null;
    errorType: string | null;
    tokenUsage: JsonObject | null;
    displayOrder: number;
};

type AgentSubagentEventPayload = {
    userId: number;
    convId: string;
    parentTurnId: string;
    parentToolCallId: string;
    parentIterationIndex: number;
    subagentId: string;
    executionType: string;
    ownerTaskId: string | null;
    displayName: string | null;
    mode: 'plan' | 'execute';
    statusMessage: string | null;
    startedAtMs: number;
    updatedAtMs: number;
    finishedAtMs: number | null;
    requestedModel: string | null;
    resultText: string | null;
    resultTextDelta: string | null;
    errorMessage: string | null;
    errorType: string | null;
    tokenUsage: JsonObject | null;
    eventType: 'subagent/spawned' | 'subagent/running' | 'subagent/completed' | 'subagent/error' | 'subagent/cancelled' | 'subagent/max_iterations' | 'subagent/abandoned';
    status: AgentSubagentStatus;
};

export type { AgentSubagentEventPayload, AgentSubagentSnapshot, AgentSubagentState, AgentSubagentStatus };
