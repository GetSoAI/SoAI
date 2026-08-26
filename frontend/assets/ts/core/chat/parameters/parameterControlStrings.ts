/* SoAI - Canonical chat request parameter control strings [frontend/assets/ts/core/chat/parameters/parameterControlStrings.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';

type ChatParameterControlsStrings = {
    systemPrompt: string;
    systemPromptPlaceholder: string;
    systemPromptHint: string;
    systemPromptLock: string;
    systemPromptLockHint: string;
    systemPromptLockLocked: string;
    systemPromptLockUnlocked: string;
    soaiSystemPrompt: string;
    soaiSystemPromptHint: string;
    enabledLabel: string;
    disabledLabel: string;
    sendParameterToggle: string;
    reasoningEffort: string;
    reasoningEffortHint: string;
    reasoningEffortNone: string;
    reasoningEffortMinimal: string;
    reasoningEffortLow: string;
    reasoningEffortMedium: string;
    reasoningEffortHigh: string;
    reasoningEffortXHigh: string;
    reasoningEffortMaximum: string;
    reasoningEffortUnsupportedSuffix: string;
    reasoningEffortUnsupportedMessage: string;
    maxCompletionTokens: string;
    maxCompletionTokensHint: string;
    agentMaxIterations: string;
    agentMaxIterationsHint: string;
    temperature: string;
    temperatureHint: string;
    topP: string;
    topPHint: string;
    frequencyPenalty: string;
    frequencyPenaltyHint: string;
    presencePenalty: string;
    presencePenaltyHint: string;
    stopSequences: string;
    stopSequencesHint: string;
    topLogprobs: string;
    topLogprobsHint: string;
    modelContextWindowTokensLabel: string;
    modelContextWindowTokensHint: string;
};

const resolveChatParameterControlStrings = (): ChatParameterControlsStrings => ({
    systemPrompt: i18n.t('chat.configuration.systemPrompt'),
    systemPromptPlaceholder: i18n.t('chat.configuration.systemPromptPlaceholder'),
    systemPromptHint: i18n.t('chat.configuration.systemPromptHint'),
    systemPromptLock: i18n.t('chat.configuration.systemPromptLock'),
    systemPromptLockHint: i18n.t('chat.configuration.systemPromptLockHint'),
    systemPromptLockLocked: i18n.t('chat.configuration.systemPromptLockLocked'),
    systemPromptLockUnlocked: i18n.t('chat.configuration.systemPromptLockUnlocked'),
    soaiSystemPrompt: i18n.t('chat.configuration.soaiSystemPrompt'),
    soaiSystemPromptHint: i18n.t('chat.configuration.soaiSystemPromptHint'),
    enabledLabel: i18n.t('chat.parameters.enabled'),
    disabledLabel: i18n.t('chat.parameters.disabled'),
    sendParameterToggle: i18n.t('chat.configuration.sendParameterToggle'),
    reasoningEffort: i18n.t('chat.configuration.reasoningEffort'),
    reasoningEffortHint: i18n.t('chat.configuration.reasoningEffortHint'),
    reasoningEffortNone: i18n.t('chat.configuration.reasoningEffortNone'),
    reasoningEffortMinimal: i18n.t('chat.configuration.reasoningEffortMinimal'),
    reasoningEffortLow: i18n.t('chat.configuration.reasoningEffortLow'),
    reasoningEffortMedium: i18n.t('chat.configuration.reasoningEffortMedium'),
    reasoningEffortHigh: i18n.t('chat.configuration.reasoningEffortHigh'),
    reasoningEffortXHigh: i18n.t('chat.configuration.reasoningEffortXHigh'),
    reasoningEffortMaximum: i18n.t('chat.configuration.reasoningEffortMaximum'),
    reasoningEffortUnsupportedSuffix: i18n.t('chat.configuration.reasoningEffortUnsupportedSuffix'),
    reasoningEffortUnsupportedMessage: i18n.t('chat.configuration.reasoningEffortUnsupportedMessage'),
    maxCompletionTokens: i18n.t('chat.configuration.maxCompletionTokens'),
    maxCompletionTokensHint: i18n.t('chat.configuration.maxCompletionTokensHint'),
    agentMaxIterations: i18n.t('chat.configuration.agentMaxIterations'),
    agentMaxIterationsHint: i18n.t('chat.configuration.agentMaxIterationsHint'),
    temperature: i18n.t('chat.configuration.temperature'),
    temperatureHint: i18n.t('chat.configuration.temperatureHint'),
    topP: i18n.t('chat.configuration.topP'),
    topPHint: i18n.t('chat.configuration.topPHint'),
    frequencyPenalty: i18n.t('chat.configuration.frequencyPenalty'),
    frequencyPenaltyHint: i18n.t('chat.configuration.frequencyPenaltyHint'),
    presencePenalty: i18n.t('chat.configuration.presencePenalty'),
    presencePenaltyHint: i18n.t('chat.configuration.presencePenaltyHint'),
    stopSequences: i18n.t('chat.configuration.stopSequences'),
    stopSequencesHint: i18n.t('chat.configuration.stopSequencesHint'),
    topLogprobs: i18n.t('chat.configuration.topLogprobs'),
    topLogprobsHint: i18n.t('chat.configuration.topLogprobsHint'),
    modelContextWindowTokensLabel: i18n.t('chat.configuration.model_settings.contextWindowTokensLabel'),
    modelContextWindowTokensHint: i18n.t('chat.configuration.model_settings.contextWindowTokensHint')
});

export { resolveChatParameterControlStrings };
export type { ChatParameterControlsStrings };
