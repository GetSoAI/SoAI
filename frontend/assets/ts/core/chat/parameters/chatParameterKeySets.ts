/* SoAI - Shared chat parameter key sets [frontend/assets/ts/core/chat/parameters/chatParameterKeySets.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatParameters } from '@core/chat/parameters/types.ts';

type ChatParameterKey = Extract<keyof ChatParameters, string>;

const LOCAL_ONLY_CHAT_PARAMETER_KEYS: ReadonlyArray<ChatParameterKey> = Object.freeze(['widescreenMode', 'richTextEnabled', 'inlineMultimediaPreviewsEnabled', 'hideRealModel', 'autoTitleGeneration', 'hideAutomationRuns', 'hideMessagingConversations', 'showActivities', 'notifyOnCompletion', 'notifyOnError', 'microphoneSoundEffectsEnabled', 'inputActionVoiceEnabled', 'inputActionCallEnabled', 'inputActionFileUploadEnabled', 'inputActionCameraEnabled', 'inputActionPromptsEnabled', 'inputActionTokenCounterEnabled', 'inputActionNewConversationEnabled', 'inputActionCharacterMapEnabled', 'inputActionMobileAuxiliaryAction', 'conversationPdfExportEnabled', 'ctrlEnterSendEnabled', 'voiceTtsModel', 'voiceSttModel', 'voiceTtsVoice', 'voiceTtsSpeed']);

const LOCAL_ONLY_CHAT_PARAMETER_KEY_SET: ReadonlySet<string> = new Set<ChatParameterKey>(LOCAL_ONLY_CHAT_PARAMETER_KEYS);

const CHAT_PRESET_PARAMETER_KEYS: ReadonlyArray<ChatParameterKey> = Object.freeze(['agentMaxIterations']);

const CHAT_PRESET_PARAMETER_KEY_SET: ReadonlySet<string> = new Set<ChatParameterKey>(CHAT_PRESET_PARAMETER_KEYS);

const EXCLUDED_REQUEST_PARAMETERS: ReadonlyArray<ChatParameterKey> = Object.freeze(['widescreenMode', 'richTextEnabled', 'inlineMultimediaPreviewsEnabled', 'textZoom', 'hideRealModel', 'autoTitleGeneration', 'hideAutomationRuns', 'hideMessagingConversations', 'showActivities', 'notifyOnCompletion', 'notifyOnError', 'microphoneSoundEffectsEnabled', 'inputActionVoiceEnabled', 'inputActionCallEnabled', 'inputActionFileUploadEnabled', 'inputActionCameraEnabled', 'inputActionPromptsEnabled', 'inputActionTokenCounterEnabled', 'inputActionNewConversationEnabled', 'inputActionCharacterMapEnabled', 'inputActionMobileAuxiliaryAction', 'conversationPdfExportEnabled', 'ctrlEnterSendEnabled', 'toolsEnabled', 'toolApprovalRequired', 'newConversationInheritLastSettings', 'voiceTtsModel', 'voiceSttModel', 'voiceTtsVoice', 'voiceTtsSpeed']);

const EXCLUDED_REQUEST_PARAMETER_KEY_SET: ReadonlySet<string> = new Set<ChatParameterKey>(EXCLUDED_REQUEST_PARAMETERS);

const BACKEND_OWNED_CHAT_PARAMETER_KEYS: ReadonlyArray<ChatParameterKey> = Object.freeze(['temperature', 'contextWindowTokens', 'maxCompletionTokens', 'topP', 'frequencyPenalty', 'presencePenalty', 'stop', 'logprobs', 'topLogprobs', 'reasoningEffort', 'serviceTier', 'completionCount']);

const BACKEND_OWNED_CHAT_PARAMETER_KEY_SET: ReadonlySet<string> = new Set<ChatParameterKey>(BACKEND_OWNED_CHAT_PARAMETER_KEYS);

type ChatParameterSendControl = {
    parameter: ChatParameterKey;
    flag: ChatParameterKey;
};

const CHAT_PARAMETER_SEND_CONTROLS: ReadonlyArray<ChatParameterSendControl> = Object.freeze([
    { parameter: 'reasoningEffort', flag: 'reasoningEffortSendEnabled' },
    { parameter: 'maxCompletionTokens', flag: 'maxCompletionTokensSendEnabled' },
    { parameter: 'topP', flag: 'topPSendEnabled' },
    { parameter: 'frequencyPenalty', flag: 'frequencyPenaltySendEnabled' },
    { parameter: 'presencePenalty', flag: 'presencePenaltySendEnabled' },
    { parameter: 'stop', flag: 'stopSendEnabled' },
    { parameter: 'logprobs', flag: 'logprobsSendEnabled' },
    { parameter: 'topLogprobs', flag: 'logprobsSendEnabled' }
]);

const CHAT_PARAMETER_SEND_FLAG_KEYS: ReadonlyArray<ChatParameterKey> = Object.freeze(['reasoningEffortSendEnabled', 'maxCompletionTokensSendEnabled', 'topPSendEnabled', 'frequencyPenaltySendEnabled', 'presencePenaltySendEnabled', 'stopSendEnabled', 'logprobsSendEnabled']);

const CHAT_PARAMETER_SEND_FLAG_KEY_SET: ReadonlySet<string> = new Set<ChatParameterKey>(CHAT_PARAMETER_SEND_FLAG_KEYS);

const STORED_CHAT_PARAMETER_KEYS: ReadonlyArray<ChatParameterKey> = Object.freeze([...BACKEND_OWNED_CHAT_PARAMETER_KEYS, ...CHAT_PARAMETER_SEND_FLAG_KEYS]);

const CHAT_STORAGE_BOOLEAN_PARAMETER_KEYS: ReadonlyArray<ChatParameterKey> = Object.freeze(['widescreenMode', 'richTextEnabled', 'inlineMultimediaPreviewsEnabled', 'autoTitleGeneration', 'hideAutomationRuns', 'hideMessagingConversations', 'showActivities', 'notifyOnCompletion', 'notifyOnError', 'microphoneSoundEffectsEnabled', 'inputActionVoiceEnabled', 'inputActionCallEnabled', 'inputActionFileUploadEnabled', 'inputActionCameraEnabled', 'inputActionPromptsEnabled', 'inputActionTokenCounterEnabled', 'inputActionNewConversationEnabled', 'inputActionCharacterMapEnabled', 'conversationPdfExportEnabled', 'ctrlEnterSendEnabled', ...CHAT_PARAMETER_SEND_FLAG_KEYS]);

const CHAT_STORAGE_BOOLEAN_PARAMETER_KEY_SET: ReadonlySet<string> = new Set<ChatParameterKey>(CHAT_STORAGE_BOOLEAN_PARAMETER_KEYS);

const CHAT_PARAMETER_TO_PREFERENCE_MAP: Readonly<Record<string, string>> = Object.freeze({
    hideRealModel: 'hide_real_model'
});

const CHAT_PREFERENCE_TO_PARAMETER_MAP: Readonly<Record<string, string>> = Object.freeze({
    'hide_real_model': 'hideRealModel'
});

const CHAT_PARAMETER_WIRE_KEYS: Readonly<Partial<Record<ChatParameterKey, string>>> = Object.freeze({
    completionCount: 'n',
    contextWindowTokens: 'context_window_tokens',
    maxCompletionTokens: 'max_completion_tokens',
    topP: 'top_p',
    frequencyPenalty: 'frequency_penalty',
    presencePenalty: 'presence_penalty',
    topLogprobs: 'top_logprobs',
    reasoningEffort: 'reasoning_effort',
    serviceTier: 'service_tier',
    reasoningEffortSendEnabled: 'reasoning_effort_send_enabled',
    maxCompletionTokensSendEnabled: 'max_completion_tokens_send_enabled',
    topPSendEnabled: 'top_p_send_enabled',
    frequencyPenaltySendEnabled: 'frequency_penalty_send_enabled',
    presencePenaltySendEnabled: 'presence_penalty_send_enabled',
    stopSendEnabled: 'stop_send_enabled',
    logprobsSendEnabled: 'logprobs_send_enabled',
    widescreenMode: 'widescreen_mode',
    richTextEnabled: 'rich_text_enabled',
    inlineMultimediaPreviewsEnabled: 'inline_multimedia_previews_enabled',
    textZoom: 'text_zoom',
    hideRealModel: 'hide_real_model',
    autoTitleGeneration: 'auto_title_generation',
    hideAutomationRuns: 'hide_automation_runs',
    hideMessagingConversations: 'hide_messaging_conversations',
    showActivities: 'show_activities',
    notifyOnCompletion: 'notify_on_completion',
    notifyOnError: 'notify_on_error',
    microphoneSoundEffectsEnabled: 'microphone_sound_effects_enabled',
    inputActionVoiceEnabled: 'input_action_voice_enabled',
    inputActionCallEnabled: 'input_action_call_enabled',
    inputActionFileUploadEnabled: 'input_action_file_upload_enabled',
    inputActionCameraEnabled: 'input_action_camera_enabled',
    inputActionPromptsEnabled: 'input_action_prompts_enabled',
    inputActionTokenCounterEnabled: 'input_action_token_counter_enabled',
    inputActionNewConversationEnabled: 'input_action_new_conversation_enabled',
    inputActionCharacterMapEnabled: 'input_action_character_map_enabled',
    inputActionMobileAuxiliaryAction: 'input_action_mobile_auxiliary_action',
    conversationPdfExportEnabled: 'conversation_pdf_export_enabled',
    ctrlEnterSendEnabled: 'ctrl_enter_send_enabled',
    toolsEnabled: 'tools_enabled',
    toolApprovalRequired: 'tool_approval_required',
    newConversationInheritLastSettings: 'new_conversation_inherit_last_settings',
    voiceTtsModel: 'voice_tts_model',
    voiceSttModel: 'voice_stt_model',
    voiceTtsVoice: 'voice_tts_voice',
    voiceTtsSpeed: 'voice_tts_speed',
    agentMaxIterations: 'agent_max_iterations'
});

const CHAT_WIRE_TO_PARAMETER_KEYS: Readonly<Record<string, ChatParameterKey>> = Object.freeze({
    n: 'completionCount',
    'context_window_tokens': 'contextWindowTokens',
    'max_completion_tokens': 'maxCompletionTokens',
    'top_p': 'topP',
    'frequency_penalty': 'frequencyPenalty',
    'presence_penalty': 'presencePenalty',
    'top_logprobs': 'topLogprobs',
    'reasoning_effort': 'reasoningEffort',
    'service_tier': 'serviceTier',
    'reasoning_effort_send_enabled': 'reasoningEffortSendEnabled',
    'max_completion_tokens_send_enabled': 'maxCompletionTokensSendEnabled',
    'top_p_send_enabled': 'topPSendEnabled',
    'frequency_penalty_send_enabled': 'frequencyPenaltySendEnabled',
    'presence_penalty_send_enabled': 'presencePenaltySendEnabled',
    'stop_send_enabled': 'stopSendEnabled',
    'logprobs_send_enabled': 'logprobsSendEnabled',
    'widescreen_mode': 'widescreenMode',
    'rich_text_enabled': 'richTextEnabled',
    'inline_multimedia_previews_enabled': 'inlineMultimediaPreviewsEnabled',
    'text_zoom': 'textZoom',
    'hide_real_model': 'hideRealModel',
    'auto_title_generation': 'autoTitleGeneration',
    'hide_automation_runs': 'hideAutomationRuns',
    'hide_messaging_conversations': 'hideMessagingConversations',
    'show_activities': 'showActivities',
    'notify_on_completion': 'notifyOnCompletion',
    'notify_on_error': 'notifyOnError',
    'microphone_sound_effects_enabled': 'microphoneSoundEffectsEnabled',
    'input_action_voice_enabled': 'inputActionVoiceEnabled',
    'input_action_call_enabled': 'inputActionCallEnabled',
    'input_action_file_upload_enabled': 'inputActionFileUploadEnabled',
    'input_action_camera_enabled': 'inputActionCameraEnabled',
    'input_action_prompts_enabled': 'inputActionPromptsEnabled',
    'input_action_token_counter_enabled': 'inputActionTokenCounterEnabled',
    'input_action_new_conversation_enabled': 'inputActionNewConversationEnabled',
    'input_action_character_map_enabled': 'inputActionCharacterMapEnabled',
    'input_action_mobile_auxiliary_action': 'inputActionMobileAuxiliaryAction',
    'conversation_pdf_export_enabled': 'conversationPdfExportEnabled',
    'ctrl_enter_send_enabled': 'ctrlEnterSendEnabled',
    'tools_enabled': 'toolsEnabled',
    'tool_approval_required': 'toolApprovalRequired',
    'new_conversation_inherit_last_settings': 'newConversationInheritLastSettings',
    'voice_tts_model': 'voiceTtsModel',
    'voice_stt_model': 'voiceSttModel',
    'voice_tts_voice': 'voiceTtsVoice',
    'voice_tts_speed': 'voiceTtsSpeed',
    'agent_max_iterations': 'agentMaxIterations'
});

export { BACKEND_OWNED_CHAT_PARAMETER_KEYS, BACKEND_OWNED_CHAT_PARAMETER_KEY_SET, CHAT_PARAMETER_SEND_CONTROLS, CHAT_PARAMETER_SEND_FLAG_KEYS, CHAT_PARAMETER_SEND_FLAG_KEY_SET, CHAT_PARAMETER_WIRE_KEYS, CHAT_WIRE_TO_PARAMETER_KEYS, CHAT_PARAMETER_TO_PREFERENCE_MAP, CHAT_PREFERENCE_TO_PARAMETER_MAP, CHAT_PRESET_PARAMETER_KEYS, CHAT_PRESET_PARAMETER_KEY_SET, CHAT_STORAGE_BOOLEAN_PARAMETER_KEYS, CHAT_STORAGE_BOOLEAN_PARAMETER_KEY_SET, EXCLUDED_REQUEST_PARAMETERS, EXCLUDED_REQUEST_PARAMETER_KEY_SET, LOCAL_ONLY_CHAT_PARAMETER_KEYS, LOCAL_ONLY_CHAT_PARAMETER_KEY_SET, STORED_CHAT_PARAMETER_KEYS };
export type { ChatParameterSendControl };
