/* SoAI - Chat feature subagent call IDs [frontend/assets/ts/features/chat/agent/subagentCallIds.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';

const SUBAGENT_PARENT_TOOL_CALL_ID_PREFIX = 'subagent:';

const buildSubagentParentToolCallId = (subagentId: string): string => {
    const normalizedSubagentId = toTrimmedString(subagentId);
    if (!normalizedSubagentId) {
        throw new Error('Subagent parent tool call id requires a subagent id.');
    }
    return `${SUBAGENT_PARENT_TOOL_CALL_ID_PREFIX}${normalizedSubagentId}`;
};

const resolveSubagentIdFromParentToolCallId = (callId: string): string | null => {
    const normalizedCallId = toTrimmedString(callId);
    if (!normalizedCallId.startsWith(SUBAGENT_PARENT_TOOL_CALL_ID_PREFIX)) {
        return null;
    }
    const subagentId = normalizedCallId.slice(SUBAGENT_PARENT_TOOL_CALL_ID_PREFIX.length).trim();
    return subagentId ? subagentId : null;
};

const isSubagentParentToolCallId = (callId: string): boolean => resolveSubagentIdFromParentToolCallId(callId) !== null;

export { buildSubagentParentToolCallId, isSubagentParentToolCallId, resolveSubagentIdFromParentToolCallId };
