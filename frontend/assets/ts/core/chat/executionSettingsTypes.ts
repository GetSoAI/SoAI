/* SoAI - Canonical Chat execution settings contracts [frontend/assets/ts/core/chat/executionSettingsTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatRequestParameters } from '@core/types/chatParameters.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { AgentMode } from '@core/chat/agentMode.ts';

type ConversationParameterSettings = Partial<ChatRequestParameters> & {
    additionalParameters?: JsonObject;
};

interface ConversationAgentSettings {
    mode?: AgentMode;
    maxIterations?: number;
    additionalSettings?: JsonObject;
}

interface ConversationMcpSettings {
    defaultTools: string[];
    planTools: string[];
    executeTools: string[];
    serverConfigs: Record<string, boolean>;
    toolsEnabled: boolean;
    toolApprovalRequired: boolean;
    additionalSettings?: JsonObject;
}

interface ConversationIdentitySettings {
    userDisplayName: string | null;
    assistantDisplayName: string | null;
    additionalSettings?: JsonObject;
}

interface ConversationPromptSettings {
    userSystemPrompt: string | null;
    userSystemPromptLockEnabled?: boolean;
    soaiSystemPromptEnabled: boolean;
    additionalSettings?: JsonObject;
}

interface ConversationModelSettings {
    model: string | null;
    comparisonModels?: string[];
    workspacePath?: string | null;
    parameters?: ConversationParameterSettings;
    agent?: ConversationAgentSettings;
    mcp?: ConversationMcpSettings;
    identity?: ConversationIdentitySettings;
    prompts?: ConversationPromptSettings;
    additionalSettings?: JsonObject;
}

interface ConversationMcpSettingsUpdate {
    defaultTools?: string[] | null;
    planTools?: string[] | null;
    executeTools?: string[] | null;
    serverConfigs?: Record<string, boolean> | null;
    toolsEnabled?: boolean | null;
    toolApprovalRequired?: boolean | null;
    additionalSettings?: JsonObject;
}

interface ConversationModelSettingsUpdate {
    model?: string | null;
    comparisonModels?: string[];
    workspacePath?: string | null;
    parameters?: ConversationParameterSettings;
    agent?: Partial<ConversationAgentSettings>;
    mcp?: ConversationMcpSettingsUpdate;
    identity?: Partial<ConversationIdentitySettings>;
    prompts?: Partial<ConversationPromptSettings>;
    additionalSettings?: JsonObject;
}

export type { ConversationAgentSettings, ConversationIdentitySettings, ConversationMcpSettings, ConversationMcpSettingsUpdate, ConversationModelSettings, ConversationModelSettingsUpdate, ConversationParameterSettings, ConversationPromptSettings };
