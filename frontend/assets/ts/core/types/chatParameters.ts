/* SoAI - Shared types chat parameters [frontend/assets/ts/core/types/chatParameters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatMobileAuxiliaryAction } from '@core/chat/parameters/mobileAuxiliaryAction.ts';
import type { ChatServiceTier } from '@core/chat/parameters/serviceTier.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

interface ChatRequestParameters {
    temperature: number;
    contextWindowTokens: number | null;
    maxCompletionTokens: number | null;
    topP: number;
    frequencyPenalty: number;
    presencePenalty: number;
    stop: string[];
    logprobs: boolean;
    topLogprobs: number | null;
    reasoningEffort: string | null;
    serviceTier: ChatServiceTier | null;
    completionCount: number;
    reasoningEffortSendEnabled: boolean;
    maxCompletionTokensSendEnabled: boolean;
    topPSendEnabled: boolean;
    frequencyPenaltySendEnabled: boolean;
    presencePenaltySendEnabled: boolean;
    stopSendEnabled: boolean;
    logprobsSendEnabled: boolean;
    [key: string]: JsonValue | undefined;
}

interface ChatUiParameters extends ChatRequestParameters {
    widescreenMode: boolean;
    richTextEnabled: boolean;
    inlineMultimediaPreviewsEnabled: boolean;
    textZoom?: number;
    hideRealModel: boolean;
    autoTitleGeneration: boolean;
    hideAutomationRuns: boolean;
    hideMessagingConversations: boolean;
    showActivities?: boolean;
    notifyOnCompletion: boolean;
    notifyOnError: boolean;
    microphoneSoundEffectsEnabled: boolean;
    inputActionVoiceEnabled: boolean;
    inputActionCallEnabled: boolean;
    inputActionFileUploadEnabled: boolean;
    inputActionCameraEnabled: boolean;
    inputActionPromptsEnabled: boolean;
    inputActionTokenCounterEnabled: boolean;
    inputActionCharacterMapEnabled: boolean;
    inputActionMobileAuxiliaryAction: ChatMobileAuxiliaryAction;
    conversationPdfExportEnabled: boolean;
    toolsEnabled: boolean;
    toolApprovalRequired: boolean;
    newConversationInheritLastSettings: boolean;
    voiceTtsModel: string | null;
    voiceSttModel: string | null;
    voiceTtsVoice?: string | null;
    voiceTtsSpeed?: number | null;
    agentMaxIterations?: number;
}

export type { ChatRequestParameters, ChatUiParameters };
