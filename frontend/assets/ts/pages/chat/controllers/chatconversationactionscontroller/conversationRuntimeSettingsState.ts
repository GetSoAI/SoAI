/* SoAI - Chat page conversation runtime settings state [frontend/assets/ts/pages/chat/controllers/chatconversationactionscontroller/conversationRuntimeSettingsState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { DEFAULT_AGENT_MAX_ITERATIONS } from '@core/chat/parameters/agentMaxIterations.ts';
import { getDefaultChatParameters, normalizeStoredParameterValue } from '@core/chat/parameters/chatParameterDefaults.ts';
import { EXCLUDED_REQUEST_PARAMETERS, STORED_CHAT_PARAMETER_KEYS } from '@core/chat/parameters/chatParameterKeySets.ts';
import { canInteractivelyAdjustConversationTools, type ChatParameters, type Conversation } from '@features/chat/public.ts';

const resolveHydratedConversationParameters = (currentParameters: ChatParameters, conversation: Conversation | null): ChatParameters => {
    const merged = { ...currentParameters };
    if (conversation === null) {
        return merged;
    }
    const defaults = getDefaultChatParameters();
    const modelSettings = conversation.modelSettings;
    for (const key of STORED_CHAT_PARAMETER_KEYS) {
        if (!EXCLUDED_REQUEST_PARAMETERS.includes(key)) {
            merged[key] = defaults[key];
        }
    }
    const storedParameters = modelSettings.parameters;
    if (storedParameters) {
        for (const [key, value] of Object.entries(storedParameters)) {
            if (key in defaults && !EXCLUDED_REQUEST_PARAMETERS.includes(key)) {
                const normalized = normalizeStoredParameterValue(key, value, defaults);
                if (normalized !== undefined) {
                    merged[key] = normalized;
                }
            }
        }
    }
    const storedMcp = modelSettings.mcp;
    if (storedMcp && canInteractivelyAdjustConversationTools(conversation)) {
        merged.toolsEnabled = storedMcp.toolsEnabled;
        merged.toolApprovalRequired = storedMcp.toolApprovalRequired;
    }
    merged.agentMaxIterations = modelSettings.agent?.maxIterations ?? DEFAULT_AGENT_MAX_ITERATIONS;
    return merged;
};

export { resolveHydratedConversationParameters };
