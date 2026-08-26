/* SoAI - Chat preset model-dependent parameter validation [frontend/assets/ts/pages/chat/controllers/chatconfigurationcontroller/chatPresetModelValidationDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveModelContextWindowLimit } from '@core/chat/modelContextWindowLimit.ts';
import type { ChatParameters } from '@features/chat/public.ts';
import type { ModelData } from '@core/types/modelTypes.ts';
import { resolveOpenAiEndpointModelId } from '@core/models/modelIdentity.ts';
import { supportsOpenAIEndpointForModel } from '@core/openai/capabilityChecks.ts';

type VoiceModelAvailability = Readonly<{ tts: ReadonlySet<string>; stt: ReadonlySet<string> }>;

const resolveVoiceModelAvailability = (models: readonly ModelData[]): VoiceModelAvailability => ({
    tts: new Set(models.filter((model) => supportsOpenAIEndpointForModel(model, 'audio_speech')).map(resolveOpenAiEndpointModelId)),
    stt: new Set(models.filter((model) => supportsOpenAIEndpointForModel(model, 'audio_transcriptions')).map(resolveOpenAiEndpointModelId))
});

const isChatPresetModelParameterStateValid = (parameters: ChatParameters, modelId: string | null, modelIndex: ReadonlyMap<string, ModelData>): boolean => {
    const model = modelId === null ? null : (modelIndex.get(modelId) ?? null);
    const contextWindowLimit = resolveModelContextWindowLimit(parameters.contextWindowTokens, model?.contextWindowTokens);
    const maximumCompletionTokens = parameters.maxCompletionTokens;
    if (parameters.maxCompletionTokensSendEnabled !== true || maximumCompletionTokens === null || contextWindowLimit === null) {
        return true;
    }
    return Number.isSafeInteger(maximumCompletionTokens) && maximumCompletionTokens >= 0 && maximumCompletionTokens <= contextWindowLimit;
};

export { isChatPresetModelParameterStateValid, resolveVoiceModelAvailability };
export type { VoiceModelAvailability };
