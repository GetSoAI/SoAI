/* SoAI - Chat feature agent subagent state rules [frontend/assets/ts/features/chat/agent/agentSubagentStateRules.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { MAX_TOOL_OUTPUT_CHARS } from '@features/chat/toolOutput.ts';
import type { AgentSubagentEventPayload, AgentSubagentSnapshot, AgentSubagentState } from '@core/chat/agentSubagentTypes.ts';
import type { AgentTurnState } from '@core/chat/agentTypes.ts';

const isTerminalSubagentStatus = (status: AgentSubagentState['status']): boolean => {
    return status === 'completed' || status === 'error' || status === 'cancelled' || status === 'max_iterations' || status === 'abandoned';
};

const hasStreamedOutput = (value: string | null): boolean => {
    if (typeof value !== 'string') {
        return false;
    }
    return value.length > 0;
};

const resolveEffectiveSubagentStatus = (status: AgentSubagentEventPayload['status'], resultText: string | null): AgentSubagentState['status'] => {
    if (status !== 'running') {
        return status;
    }
    return hasStreamedOutput(resultText) ? 'running' : 'accepted';
};

const resolveSubagentStatusRank = (status: AgentSubagentState['status']): number => {
    if (status === 'accepted') {
        return 0;
    }
    if (status === 'running') {
        return 1;
    }
    return 2;
};

const shouldApplySubagentSnapshot = (existing: AgentSubagentState | undefined, snapshot: AgentSubagentSnapshot): boolean => {
    if (!existing) {
        return true;
    }
    if (isTerminalSubagentStatus(snapshot.status)) {
        if (isTerminalSubagentStatus(existing.status) && snapshot.status !== existing.status) {
            return false;
        }
        return snapshot.updatedAtMs >= existing.updatedAtMs;
    }
    if (isTerminalSubagentStatus(existing.status) && snapshot.status === existing.status) {
        return snapshot.updatedAtMs >= existing.updatedAtMs;
    }
    if (isTerminalSubagentStatus(existing.status) && snapshot.status !== existing.status) {
        return false;
    }
    if (resolveSubagentStatusRank(snapshot.status) > resolveSubagentStatusRank(existing.status)) {
        return true;
    }
    if (resolveSubagentStatusRank(snapshot.status) < resolveSubagentStatusRank(existing.status)) {
        return false;
    }
    return snapshot.updatedAtMs >= existing.updatedAtMs;
};

const resolveSubagentDisplayOrder = (turnState: AgentTurnState, existing: AgentSubagentState | undefined): number => {
    if (existing) {
        return existing.displayOrder;
    }
    const displayOrder = turnState.subagentDisplayCounter;
    turnState.subagentDisplayCounter += 1;
    return displayOrder;
};

const capResultTextTail = (value: string): string => {
    if (value.length <= MAX_TOOL_OUTPUT_CHARS) {
        return value;
    }
    return value.slice(value.length - MAX_TOOL_OUTPUT_CHARS);
};

const mergeResultText = (existingText: string | null, incomingText: string | null): string | null => {
    const cappedIncoming = typeof incomingText === 'string' ? capResultTextTail(incomingText) : null;
    const cappedExisting = typeof existingText === 'string' ? capResultTextTail(existingText) : null;
    if (cappedIncoming === null) {
        return cappedExisting;
    }
    if (cappedExisting === null) {
        return cappedIncoming;
    }
    if (cappedIncoming.length > cappedExisting.length) {
        return cappedIncoming;
    }
    if (cappedIncoming.length === cappedExisting.length && cappedIncoming.length === MAX_TOOL_OUTPUT_CHARS) {
        return cappedIncoming;
    }
    return cappedExisting;
};

export { capResultTextTail, hasStreamedOutput, isTerminalSubagentStatus, mergeResultText, resolveEffectiveSubagentStatus, resolveSubagentDisplayOrder, resolveSubagentStatusRank, shouldApplySubagentSnapshot };
