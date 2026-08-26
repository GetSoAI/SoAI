/* SoAI - Chat feature agent mode state [frontend/assets/ts/features/chat/agent/agentModeState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { cycleAgentMode, isAgentMode, isToolAgentMode, type AgentMode } from '@core/chat/agentMode.ts';
import type { ConversationModelSettings } from '@core/chat/executionSettingsTypes.ts';

const resolveAgentModeFromModelSettings = (modelSettings: ConversationModelSettings | null | undefined): AgentMode => modelSettings?.agent?.mode ?? 'chat';

const resolveAgentMode = (conversation: { modelSettings?: ConversationModelSettings } | null | undefined): AgentMode => resolveAgentModeFromModelSettings(conversation?.modelSettings);

export { isAgentMode, isToolAgentMode, resolveAgentMode, resolveAgentModeFromModelSettings, cycleAgentMode };
