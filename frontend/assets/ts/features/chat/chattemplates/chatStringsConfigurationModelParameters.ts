/* SoAI - Chat feature strings configuration model parameters [frontend/assets/ts/features/chat/chattemplates/chatStringsConfigurationModelParameters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SanitizerApi } from '@core/pagecontext/public.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ChatTemplateStringSet } from '@features/chat/chattemplates/stringSetTypes.ts';

type ModelParameters = Pick<
    ChatTemplateStringSet,
    | 'temperature'
    | 'temperatureFocused'
    | 'temperatureBalanced'
    | 'temperatureCreative'
    | 'maxTokens'
    | 'enabledLabel'
    | 'disabledLabel'
    | 'enabledLabelAttr'
    | 'disabledLabelAttr'
    | 'sendParameterToggle'
    | 'topP'
    | 'frequencyPenalty'
    | 'presencePenalty'
    | 'systemPromptHint'
    | 'maxTokensHint'
    | 'temperatureHint'
    | 'topPHint'
    | 'frequencyPenaltyHint'
    | 'presencePenaltyHint'
    | 'seed'
    | 'seedHint'
    | 'stopSequences'
    | 'stopSequencesHint'
    | 'topLogprobs'
    | 'topLogprobsHint'
    | 'maxCompletionTokens'
    | 'maxCompletionTokensHint'
    | 'agentMaxIterations'
    | 'agentMaxIterationsHint'
    | 'reasoningEffort'
    | 'reasoningEffortHint'
    | 'reasoningEffortNone'
    | 'reasoningEffortMinimal'
    | 'reasoningEffortLow'
    | 'reasoningEffortMedium'
    | 'reasoningEffortHigh'
    | 'reasoningEffortXHigh'
    | 'reasoningEffortMaximum'
    | 'reasoningEffortUnsupportedSuffix'
    | 'reasoningEffortUnsupportedMessage'
    | 'serviceTier'
    | 'serviceTierHint'
    | 'serviceTierUnset'
    | 'serviceTierAuto'
    | 'serviceTierDefault'
    | 'serviceTierFlex'
    | 'serviceTierPriority'
    | 'advancedParameters'
>;

const resolveConfigurationModelParametersTemplateStrings = (sanitizer: SanitizerApi): ModelParameters => {
    return {
        temperature: i18n.html(sanitizer, 'chat.configuration.temperature'),
        temperatureFocused: i18n.html(sanitizer, 'chat.configuration.temperatureFocused'),
        temperatureBalanced: i18n.html(sanitizer, 'chat.configuration.temperatureBalanced'),
        temperatureCreative: i18n.html(sanitizer, 'chat.configuration.temperatureCreative'),
        maxTokens: i18n.html(sanitizer, 'chat.configuration.maxTokens'),
        enabledLabel: i18n.html(sanitizer, 'chat.parameters.enabled'),
        disabledLabel: i18n.html(sanitizer, 'chat.parameters.disabled'),
        enabledLabelAttr: i18n.attr(sanitizer, 'chat.parameters.enabled'),
        disabledLabelAttr: i18n.attr(sanitizer, 'chat.parameters.disabled'),
        sendParameterToggle: i18n.html(sanitizer, 'chat.configuration.sendParameterToggle'),
        topP: i18n.html(sanitizer, 'chat.configuration.topP'),
        frequencyPenalty: i18n.html(sanitizer, 'chat.configuration.frequencyPenalty'),
        presencePenalty: i18n.html(sanitizer, 'chat.configuration.presencePenalty'),
        systemPromptHint: i18n.html(sanitizer, 'chat.configuration.systemPromptHint'),
        maxTokensHint: i18n.html(sanitizer, 'chat.configuration.maxTokensHint'),
        temperatureHint: i18n.html(sanitizer, 'chat.configuration.temperatureHint'),
        topPHint: i18n.html(sanitizer, 'chat.configuration.topPHint'),
        frequencyPenaltyHint: i18n.html(sanitizer, 'chat.configuration.frequencyPenaltyHint'),
        presencePenaltyHint: i18n.html(sanitizer, 'chat.configuration.presencePenaltyHint'),
        seed: i18n.html(sanitizer, 'chat.configuration.seed'),
        seedHint: i18n.html(sanitizer, 'chat.configuration.seedHint'),
        stopSequences: i18n.html(sanitizer, 'chat.configuration.stopSequences'),
        stopSequencesHint: i18n.html(sanitizer, 'chat.configuration.stopSequencesHint'),
        topLogprobs: i18n.html(sanitizer, 'chat.configuration.topLogprobs'),
        topLogprobsHint: i18n.html(sanitizer, 'chat.configuration.topLogprobsHint'),
        maxCompletionTokens: i18n.html(sanitizer, 'chat.configuration.maxCompletionTokens'),
        maxCompletionTokensHint: i18n.html(sanitizer, 'chat.configuration.maxCompletionTokensHint'),
        agentMaxIterations: i18n.html(sanitizer, 'chat.configuration.agentMaxIterations'),
        agentMaxIterationsHint: i18n.html(sanitizer, 'chat.configuration.agentMaxIterationsHint'),
        reasoningEffort: i18n.html(sanitizer, 'chat.configuration.reasoningEffort'),
        reasoningEffortHint: i18n.html(sanitizer, 'chat.configuration.reasoningEffortHint'),
        reasoningEffortNone: i18n.html(sanitizer, 'chat.configuration.reasoningEffortNone'),
        reasoningEffortMinimal: i18n.html(sanitizer, 'chat.configuration.reasoningEffortMinimal'),
        reasoningEffortLow: i18n.html(sanitizer, 'chat.configuration.reasoningEffortLow'),
        reasoningEffortMedium: i18n.html(sanitizer, 'chat.configuration.reasoningEffortMedium'),
        reasoningEffortHigh: i18n.html(sanitizer, 'chat.configuration.reasoningEffortHigh'),
        reasoningEffortXHigh: i18n.html(sanitizer, 'chat.configuration.reasoningEffortXHigh'),
        reasoningEffortMaximum: i18n.html(sanitizer, 'chat.configuration.reasoningEffortMaximum'),
        reasoningEffortUnsupportedSuffix: i18n.html(sanitizer, 'chat.configuration.reasoningEffortUnsupportedSuffix'),
        reasoningEffortUnsupportedMessage: i18n.html(sanitizer, 'chat.configuration.reasoningEffortUnsupportedMessage'),
        serviceTier: i18n.html(sanitizer, 'chat.configuration.serviceTier.label'),
        serviceTierHint: i18n.html(sanitizer, 'chat.configuration.serviceTier.hint'),
        serviceTierUnset: i18n.html(sanitizer, 'chat.configuration.serviceTier.unset'),
        serviceTierAuto: i18n.html(sanitizer, 'chat.configuration.serviceTier.auto'),
        serviceTierDefault: i18n.html(sanitizer, 'chat.configuration.serviceTier.default'),
        serviceTierFlex: i18n.html(sanitizer, 'chat.configuration.serviceTier.flex'),
        serviceTierPriority: i18n.html(sanitizer, 'chat.configuration.serviceTier.priority'),
        advancedParameters: i18n.html(sanitizer, 'chat.configuration.advancedParameters')
    };
};

export { resolveConfigurationModelParametersTemplateStrings };
