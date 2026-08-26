/* SoAI - Frontend chat agent domain types [frontend/assets/ts/core/chat/agentTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AgentSubagentState } from '@core/chat/agentSubagentTypes.ts';
import type { ToolActivityCodeDiff } from '@core/chat/codeDiffParsing.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { AgentMode } from '@core/chat/agentMode.ts';

type AgentPlanStepStatus = 'pending' | 'in_progress' | 'completed';

type AgentTurnStatus = 'running' | 'completed' | 'error';
type AgentTurnSnapshotStatus = 'running' | 'completed' | 'error' | 'cancelled' | 'max_iterations' | 'abandoned';

type AgentToolCallStatus = 'pending' | 'running' | 'completed' | 'cancelled' | 'error';

type AgentPlanStep = {
    step: string;
    status: AgentPlanStepStatus;
};

type AgentCanonicalPlan = {
    revision: number | null;
    title: string | null;
    markdown: string;
};

type AgentIterationToolCall = {
    toolCallId: string;
    toolName: string;
    inputArguments: string | null;
    codeDiffs: ToolActivityCodeDiff[];
    status: AgentToolCallStatus;
    result: JsonValue | null | undefined | null;
    textLengthBefore: number;
    startedSequence: number;
    lastSequence: number;
    startedAtMs: number | null;
    durationMs: number | null;
};

type AgentIteration = {
    iterationIndex: number;
    itemId: string | null;
    text: string;
    toolCalls: AgentIterationToolCall[];
    status: AgentTurnStatus;
};

type AgentTurnState = {
    turnId: string;
    convId: string;
    mode: AgentMode;
    maxIterations: number;
    messageIndex: number | null;
    turnStartedAtMs: number;
    iterations: Map<number, AgentIteration>;
    subagents: Map<string, AgentSubagentState>;
    subagentDisplayCounter: number;
    lastSequence: number;
    status: AgentTurnStatus;
    todo: AgentPlanStep[];
    todoExplanation: string | null;
};

type AgentTurnStartedPayload = {
    userId: number;
    convId: string;
    turnId: string;
    iterationIndex: number;
    sequence: number;
    mode: AgentMode;
    maxIterations: number;
    itemId: string | null;
    eventType: string;
    status: string;
};

type AgentItemStartedPayload = {
    userId: number;
    convId: string;
    turnId: string;
    itemId: string;
    iterationIndex: number;
    sequence: number;
    itemType: string;
    eventType: string;
    status: string;
};

type AgentItemDeltaPayload = {
    userId: number;
    convId: string;
    turnId: string;
    itemId: string;
    iterationIndex: number;
    sequence: number;
    textDelta: string;
    eventType: string;
    status: string;
};

type AgentItemCompletedPayload = {
    userId: number;
    convId: string;
    turnId: string;
    itemId: string;
    iterationIndex: number;
    sequence: number;
    finalText: string;
    eventType: string;
    status: string;
};

type AgentToolCallStartedPayload = {
    userId: number;
    convId: string;
    turnId: string;
    itemId: string;
    iterationIndex: number;
    messageIndex: number;
    sequence: number;
    toolCallId: string;
    toolName: string;
    startedAtMs: number;
    toolArguments: string | null;
    eventType: string;
    status: 'running';
};

type AgentToolCallCreatedPayload = {
    userId: number;
    convId: string;
    turnId: string;
    itemId: string;
    iterationIndex: number;
    messageIndex: number;
    sequence: number;
    toolCallId: string;
    toolName: string;
    toolArguments: string | null;
    eventType: string;
    status: 'pending';
};

type AgentToolCallRunningPayload = {
    userId: number;
    convId: string;
    turnId: string;
    itemId: string;
    iterationIndex: number;
    sequence: number;
    toolCallId: string;
    toolName: string;
    startedAtMs: number;
    durationMs: number;
    eventType: string;
    status: 'running';
};

type AgentToolCallCompletedPayload = {
    userId: number;
    convId: string;
    turnId: string;
    itemId: string;
    iterationIndex: number;
    messageIndex: number;
    sequence: number;
    toolCallId: string;
    toolName: string;
    startedAtMs: number | null;
    durationMs: number | null;
    result: JsonValue | null | undefined | null;
    toolArguments: string | null;
    codeDiffs: ToolActivityCodeDiff[] | null;
    eventType: string;
    status: 'completed' | 'cancelled' | 'error';
};

type AgentTurnCompletedPayload = {
    userId: number;
    convId: string;
    turnId: string;
    iterationIndex: number;
    sequence: number;
    totalIterations: number;
    reachedMaxIterations: boolean;
    itemId: string | null;
    eventType: string;
    status: string;
};

type AgentTurnErrorPayload = {
    userId: number;
    convId: string;
    turnId: string;
    iterationIndex: number;
    sequence: number;
    message: string;
    errorType: string;
    itemId: string | null;
    eventType: string;
    status: string;
};

type AgentTodoUpdatedPayload = {
    userId: number;
    convId: string;
    turnId: string;
    iterationIndex: number;
    sequence: number;
    revision: number;
    explanation: string | null;
    todo: AgentPlanStep[];
    itemId: string | null;
    eventType: string;
    status: string;
};

type AgentPlanUpdatedPayload = {
    userId: number;
    convId: string;
    turnId: string;
    iterationIndex: number;
    sequence: number;
    revision: number;
    title: string | null;
    markdown: string;
    itemId: string | null;
    eventType: string;
    status: string;
};

type AgentModeChangedPayload = {
    userId: number;
    convId: string;
    turnId: string;
    iterationIndex: number;
    sequence: number;
    mode: AgentMode;
    itemId: string | null;
    eventType: string;
    status: string;
};

export type { AgentCanonicalPlan, AgentPlanStepStatus, AgentTurnStatus, AgentTurnSnapshotStatus, AgentToolCallStatus, AgentPlanStep, AgentIterationToolCall, AgentIteration, AgentTurnState, AgentTurnStartedPayload, AgentItemStartedPayload, AgentItemDeltaPayload, AgentItemCompletedPayload, AgentToolCallCreatedPayload, AgentToolCallStartedPayload, AgentToolCallRunningPayload, AgentToolCallCompletedPayload, AgentTurnCompletedPayload, AgentTurnErrorPayload, AgentTodoUpdatedPayload, AgentPlanUpdatedPayload, AgentModeChangedPayload };
