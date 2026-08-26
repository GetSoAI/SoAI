/* SoAI - Chat feature state runtime [frontend/assets/ts/features/chat/conversationsettings/ragconversationsettings/service/stateRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RagConfigResponse } from '@core/api/contracts/webuiRagContracts.ts';
import { parseRagLoadResult } from '@features/chat/conversationsettings/ragconversationsettings/effects.ts';
import type { RagConfig } from '@features/chat/conversationsettings/settingsModels.ts';
import type { ConversationSettingsHost } from '@features/chat/conversationsettings/conversationSettingsHost.ts';
import type { RagConfigUpdateCallbacks } from '@features/chat/conversationsettings/ragconversationsettings/contracts.ts';

interface ApplyRagLoadStateArguments {
    host: ConversationSettingsHost;
    callbacks: RagConfigUpdateCallbacks;
    configResult: PromiseSettledResult<RagConfigResponse>;
    writeBaselineConfig: (config: RagConfig | null) => void;
    renderConfig: (config: RagConfig) => void;
    resetUI: () => void;
    syncDerivedStates: () => void;
}

interface ResetRagConversationStateArguments {
    callbacks: RagConfigUpdateCallbacks;
    writeBaselineConfig: (config: RagConfig | null) => void;
}

const applyRagLoadState = (inputArguments: ApplyRagLoadStateArguments): void => {
    const parsed = parseRagLoadResult({
        host: inputArguments.host,
        configResult: inputArguments.configResult
    });
    if (!parsed.baselineConfig) {
        inputArguments.resetUI();
        inputArguments.syncDerivedStates();
        return;
    }
    inputArguments.writeBaselineConfig(parsed.baselineConfig);
    inputArguments.callbacks.onBaselineConfigChange(parsed.baselineConfig);
    inputArguments.renderConfig(parsed.baselineConfig);
    inputArguments.syncDerivedStates();
};

const resetRagConversationState = (inputArguments: ResetRagConversationStateArguments): void => {
    inputArguments.writeBaselineConfig(null);
    inputArguments.callbacks.onBaselineConfigChange(null);
    inputArguments.callbacks.onDirtyStateChange(false);
};

export { applyRagLoadState, resetRagConversationState };
