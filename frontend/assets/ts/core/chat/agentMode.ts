/* SoAI - Shared chat agent mode contract [frontend/assets/ts/core/chat/agentMode.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readAllowedStringValue } from '@core/types/payloadValueReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

type AgentMode = 'chat' | 'plan' | 'execute';

const AGENT_MODES: readonly AgentMode[] = Object.freeze(['chat', 'plan', 'execute']);

const isAgentMode = (value: JsonValue | null | undefined): value is AgentMode => readAllowedStringValue(value, AGENT_MODES) !== null;

const isToolAgentMode = (mode: AgentMode): mode is 'plan' | 'execute' => mode === 'plan' || mode === 'execute';

const NEXT_MODE_MAP: Readonly<Record<AgentMode, AgentMode>> = Object.freeze({
    chat: 'plan',
    plan: 'execute',
    execute: 'chat'
});

const cycleAgentMode = (current: AgentMode): AgentMode => NEXT_MODE_MAP[current];

export { cycleAgentMode, isAgentMode, isToolAgentMode };
export type { AgentMode };
