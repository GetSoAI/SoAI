/* SoAI - Canonical chat execution model preflight and state mutation helpers [frontend/assets/ts/features/chat/modelExecutionPreflight.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import { i18n } from '@core/i18n/index.ts';
import { showUserError } from '@core/ui/notifications/notifications.ts';
import type { AgentMode } from '@core/chat/agentMode.ts';
import type { ConversationContract } from '@features/chat/ChatTypes.ts';
import { resolveNormalizedComparisonModelIdsFromModelSettings } from '@core/chat/comparisonModels.ts';
import { isChatConversationSettingsWritable } from '@features/chat/conversation/conversationSettingsEligibility.ts';
import type { ConversationModelSettings } from '@core/chat/executionSettingsTypes.ts';

type ChatExecutionModelPreflightBlockReason = 'noModelSelected' | 'primaryModelUnavailable' | 'comparisonModelUnavailable' | 'comparisonModelsUnavailable';

type ChatExecutionModelPreflightResult = { status: 'ok'; primaryModelId: string; comparisonModelIds: string[] } | { status: 'blocked'; reason: ChatExecutionModelPreflightBlockReason };
type ChatExecutionModelSelectionPreflightResult = { status: 'ok'; primaryModelId: string } | { status: 'blocked'; reason: 'noModelSelected' | 'primaryModelUnavailable' };
type ChatExecutionModelPlan = Extract<ChatExecutionModelPreflightResult, { status: 'ok' }>;

class ChatExecutionModelPreflightBlockedError extends Error {
    readonly reason: ChatExecutionModelPreflightBlockReason;

    constructor(reason: ChatExecutionModelPreflightBlockReason) {
        super(`Chat execution blocked: ${reason}`);
        this.reason = reason;
    }
}

const normalizeChatExecutionString = (value: string | null | undefined): string | null => {
    if (!isString(value)) {
        return null;
    }
    const trimmed = value.trim();
    return trimmed ? trimmed : null;
};

const normalizeChatExecutionModelId = (value: string | null | undefined): string | null => normalizeChatExecutionString(value);

const resolveConversationStoredModelId = (conversation: ConversationContract): string | null => {
    const storedValue = conversation.modelSettings?.model ?? null;
    return normalizeChatExecutionModelId(storedValue);
};

const resolvePrimaryModelIdForExecution = (inputArguments: { selectedModelId: string | null; conversation: ConversationContract }): string | null => {
    const selected = normalizeChatExecutionModelId(inputArguments.selectedModelId);
    if (selected) {
        return selected;
    }
    return resolveConversationStoredModelId(inputArguments.conversation);
};

const resolveComparisonModelIdsForExecution = (inputArguments: { conversation: ConversationContract; primaryModelId: string }): string[] => {
    const modelSettingsValue = inputArguments.conversation.modelSettings ?? null;
    return resolveNormalizedComparisonModelIdsFromModelSettings({
        modelSettings: modelSettingsValue,
        primaryModelId: inputArguments.primaryModelId
    });
};

const preflightChatExecutionModelSelection = (inputArguments: { selectedModelId: string | null; modelStreamHasPayload: boolean; isModelAvailable: (modelId: string) => boolean }): ChatExecutionModelSelectionPreflightResult => {
    const primaryModelId = normalizeChatExecutionModelId(inputArguments.selectedModelId);
    if (!primaryModelId) {
        return { status: 'blocked', reason: 'noModelSelected' };
    }
    if (inputArguments.modelStreamHasPayload && !inputArguments.isModelAvailable(primaryModelId)) {
        return { status: 'blocked', reason: 'primaryModelUnavailable' };
    }
    return { status: 'ok', primaryModelId };
};

const preflightChatExecutionModels = (inputArguments: { conversation: ConversationContract; selectedModelId: string | null; modelStreamHasPayload: boolean; isModelAvailable: (modelId: string) => boolean }): ChatExecutionModelPreflightResult => {
    const resolvedPrimaryModelId = resolvePrimaryModelIdForExecution({ selectedModelId: inputArguments.selectedModelId, conversation: inputArguments.conversation });
    const selectionPreflight = preflightChatExecutionModelSelection({
        selectedModelId: resolvedPrimaryModelId,
        modelStreamHasPayload: inputArguments.modelStreamHasPayload,
        isModelAvailable: inputArguments.isModelAvailable
    });
    if (selectionPreflight.status === 'blocked') {
        return selectionPreflight;
    }
    const primaryModelId = selectionPreflight.primaryModelId;

    const comparisonModelIds = resolveComparisonModelIdsForExecution({ conversation: inputArguments.conversation, primaryModelId });
    if (!inputArguments.modelStreamHasPayload) {
        return { status: 'ok', primaryModelId, comparisonModelIds };
    }

    const unavailableComparison = comparisonModelIds.filter((modelId) => !inputArguments.isModelAvailable(modelId));
    if (unavailableComparison.length === 1) {
        return { status: 'blocked', reason: 'comparisonModelUnavailable' };
    }
    if (unavailableComparison.length > 1) {
        return { status: 'blocked', reason: 'comparisonModelsUnavailable' };
    }

    return { status: 'ok', primaryModelId, comparisonModelIds };
};

const requireChatExecutionModelPreflight = (inputArguments: { conversation: ConversationContract; selectedModelId: string | null; modelStreamHasPayload: boolean; isModelAvailable: (modelId: string) => boolean }): ChatExecutionModelPlan => {
    const preflight = preflightChatExecutionModels(inputArguments);
    if (preflight.status === 'blocked') {
        throw new ChatExecutionModelPreflightBlockedError(preflight.reason);
    }
    return preflight;
};

const requireNoActiveConversationExecution = (inputArguments: { conversationId: string; isConversationExecuting: (conversationId: string) => boolean; context: string }): void => {
    const conversationId = normalizeChatExecutionString(inputArguments.conversationId);
    if (!conversationId) {
        throw new Error(`${inputArguments.context} requires a conversation id`);
    }
    if (inputArguments.isConversationExecuting(conversationId)) {
        throw new Error(`${inputArguments.context} requires no active conversation execution`);
    }
};

const resolveMutableChatExecutionModelSettings = (conversation: ConversationContract): ConversationModelSettings => {
    const modelSettingsValue = conversation.modelSettings;
    if (modelSettingsValue === undefined || modelSettingsValue === null) {
        return { model: null };
    }
    return modelSettingsValue;
};

const applyPrimaryChatExecutionModelToConversation = (conversation: ConversationContract, primaryModelId: string): void => {
    if (!isChatConversationSettingsWritable(conversation)) {
        return;
    }
    const modelSettings = resolveMutableChatExecutionModelSettings(conversation);
    if (modelSettings.model === primaryModelId) {
        return;
    }
    conversation.modelSettings = {
        ...modelSettings,
        model: primaryModelId
    };
};

const applyChatExecutionModelStateToConversation = (conversation: ConversationContract, inputArguments: { primaryModelId: string; agentMode: AgentMode }): void => {
    if (!isChatConversationSettingsWritable(conversation)) {
        return;
    }
    const modelSettings = resolveMutableChatExecutionModelSettings(conversation);
    const agentSettings = modelSettings.agent ?? {};
    conversation.modelSettings = {
        ...modelSettings,
        model: inputArguments.primaryModelId,
        agent: {
            ...agentSettings,
            mode: inputArguments.agentMode
        }
    };
};

const showChatExecutionModelPreflightBlockedError = (reason: ChatExecutionModelPreflightBlockReason): void => {
    switch (reason) {
        case 'noModelSelected':
            showUserError(i18n.t('chat.stream.noModelSelected'));
            return;
        case 'primaryModelUnavailable':
            showUserError(i18n.t('chat.stream.modelUnavailable'));
            return;
        case 'comparisonModelUnavailable':
            showUserError(i18n.t('chat.stream.comparisonModelUnavailable'));
            return;
        case 'comparisonModelsUnavailable':
            showUserError(i18n.t('chat.stream.comparisonModelsUnavailable'));
            return;
    }
};

const runChatExecutionModelPreflightBoundary = async (operation: () => Promise<void>): Promise<boolean> => {
    try {
        await operation();
        return true;
    } catch (error) {
        if (error instanceof ChatExecutionModelPreflightBlockedError) {
            showChatExecutionModelPreflightBlockedError(error.reason);
            return false;
        }
        throw error;
    }
};

export { applyChatExecutionModelStateToConversation, applyPrimaryChatExecutionModelToConversation, normalizeChatExecutionModelId, preflightChatExecutionModelSelection, preflightChatExecutionModels, requireChatExecutionModelPreflight, requireNoActiveConversationExecution, resolvePrimaryModelIdForExecution, runChatExecutionModelPreflightBoundary };
export { showChatExecutionModelPreflightBlockedError };
export { ChatExecutionModelPreflightBlockedError };
export type { ChatExecutionModelPlan, ChatExecutionModelPreflightResult, ChatExecutionModelPreflightBlockReason };
