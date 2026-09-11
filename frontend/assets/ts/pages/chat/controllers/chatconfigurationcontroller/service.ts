/* SoAI - Chat configuration controller service [frontend/assets/ts/pages/chat/controllers/chatconfigurationcontroller/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isBackendOwnedNoConversationParameter, isInputActionParameter, type CommitConfigurationEditStateResult } from '@pages/chat/controllers/chatconfigurationcontroller/effects.ts';
import type { ConfigurationControllerHost, ConfigurationControllerStateAccess } from '@pages/chat/controllers/chatconfigurationcontroller/types.ts';

type ConfigurationProjectionEffect = 'storage' | 'parameters' | 'widescreen' | 'input-actions' | 'worker-rendering' | 'markup' | 'conversation-render' | 'conversation-list';

const refreshConfigurationParameterUi = (stateAccess: ConfigurationControllerStateAccess): void => {
    stateAccess.getParameterManager()?.updateParameterUI?.();
};

const runAsyncConfigurationSideEffect = (operationId: string, operation: Promise<void>): void => {
    operation.catch((error): void => errorHandler.warn('ChatPage', `Chat configuration side effect failed: ${operationId}`, ensureError(error)));
};

const requiredConfigurationProjectionEffects = (commitState: CommitConfigurationEditStateResult): ConfigurationProjectionEffect[] => {
    const effects: ConfigurationProjectionEffect[] = ['storage', 'parameters', 'widescreen'];
    if (commitState.inputActionsChanged) effects.push('input-actions');
    if (commitState.sendHotkeyChanged) effects.push('conversation-render');
    if (commitState.richTextChanged) effects.push('worker-rendering');
    if (commitState.richTextChanged || commitState.senderLabelChanged) effects.push('markup', 'conversation-render');
    if (commitState.conversationListFiltersChanged) effects.push('conversation-list');
    return effects;
};

const applyConfigurationCommitSideEffects = async (
    commitState: CommitConfigurationEditStateResult,
    dependencies: {
        stateAccess: ConfigurationControllerStateAccess;
        host: Pick<ConfigurationControllerHost, 'applyWidescreenMode' | 'applyInputActionVisibility' | 'invalidateChatMarkup' | 'renderCurrentConversation' | 'refreshConversationsUI' | 'refreshChatWorkerRendering'>;
    },
    retainedEffects: readonly ConfigurationProjectionEffect[] = [],
    includeCommitEffects = true
): Promise<readonly ConfigurationProjectionEffect[]> => {
    const commitEffects = includeCommitEffects ? requiredConfigurationProjectionEffects(commitState) : [];
    const effects = [...new Set([...retainedEffects, ...commitEffects])];
    const failed: ConfigurationProjectionEffect[] = [];
    for (const effect of effects) {
        try {
            if (effect === 'storage') dependencies.stateAccess.getStorageManager()?.saveState?.(true);
            else if (effect === 'parameters') refreshConfigurationParameterUi(dependencies.stateAccess);
            else if (effect === 'widescreen') dependencies.host.applyWidescreenMode();
            else if (effect === 'input-actions') dependencies.host.applyInputActionVisibility();
            else if (effect === 'worker-rendering') dependencies.host.refreshChatWorkerRendering();
            else if (effect === 'markup') dependencies.host.invalidateChatMarkup('current');
            else if (effect === 'conversation-render') await dependencies.host.renderCurrentConversation();
            else await dependencies.host.refreshConversationsUI();
        } catch (error) {
            failed.push(effect);
            errorHandler.warn('ChatPage', `Chat configuration projection failed: ${effect}`, ensureError(error));
        }
    }
    return failed;
};

const applyConfigurationParameterSideEffects = (
    parameter: string,
    dependencies: {
        isEditingConfiguration: () => boolean;
        stateAccess: ConfigurationControllerStateAccess;
        host: Pick<ConfigurationControllerHost, 'applyWidescreenMode' | 'applyInputActionVisibility' | 'syncToolsEnabledToConversation' | 'syncToolApprovalRequiredToConversation' | 'persistBackendChatPreferences'>;
        recalculateDirtyState: () => void;
    }
): void => {
    if (dependencies.isEditingConfiguration()) {
        dependencies.recalculateDirtyState();
        return;
    }
    dependencies.stateAccess.getStorageManager()?.savePreferences?.();
    if (parameter === 'widescreen_mode') {
        dependencies.host.applyWidescreenMode();
    }
    if (isInputActionParameter(parameter)) {
        dependencies.host.applyInputActionVisibility();
    }
    if (parameter === 'tools_enabled') {
        dependencies.host.syncToolsEnabledToConversation(dependencies.stateAccess.getParameters().toolsEnabled === true);
    }
    if (parameter === 'tool_approval_required') {
        dependencies.host.syncToolApprovalRequiredToConversation(dependencies.stateAccess.getParameters().toolApprovalRequired === true);
    }
    if (!dependencies.stateAccess.hasWritableCurrentConversation() && isBackendOwnedNoConversationParameter(parameter)) {
        runAsyncConfigurationSideEffect('chat:persistBackendChatPreferences', dependencies.host.persistBackendChatPreferences());
    }
};

export { applyConfigurationCommitSideEffects, applyConfigurationParameterSideEffects, refreshConfigurationParameterUi };
export type { ConfigurationProjectionEffect };
