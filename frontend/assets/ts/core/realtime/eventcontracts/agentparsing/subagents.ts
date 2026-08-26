/* SoAI - Frontend agent subagent event decoding [frontend/assets/ts/core/realtime/eventcontracts/agentparsing/subagents.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseAgentSubagentEventPayload } from '@core/realtime/eventcontracts/agentparsing/subagentFields.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { AgentSubagentEventPayload } from '@core/chat/agentSubagentTypes.ts';

const parseAgentSubagentPayload = (data: JsonValue): AgentSubagentEventPayload | null => {
    return parseAgentSubagentEventPayload(data);
};

export { parseAgentSubagentPayload };
