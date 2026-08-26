/* SoAI - Chat feature strings input actions voice [frontend/assets/ts/features/chat/chattemplates/chatStringsInputActionsVoice.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SanitizerApi } from '@core/pagecontext/public.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ChatTemplateStringSet } from '@features/chat/chattemplates/stringSetTypes.ts';

type InputActionsVoice = Pick<
    ChatTemplateStringSet,
    | 'notifyOnCompletion'
    | 'notifyOnError'
    | 'notifyOnCompletionHint'
    | 'notifyOnErrorHint'
    | 'microphoneSoundEffects'
    | 'microphoneSoundEffectsHint'
    | 'inputActionsTitle'
    | 'inputActionVoice'
    | 'inputActionVoiceHint'
    | 'inputActionCall'
    | 'inputActionCallHint'
    | 'inputActionUploadFile'
    | 'inputActionUploadFileHint'
    | 'inputActionCamera'
    | 'inputActionCameraHint'
    | 'inputActionCharacterMap'
    | 'inputActionCharacterMapHint'
    | 'inputActionPrompts'
    | 'inputActionPromptsHint'
    | 'inputActionTokenCounter'
    | 'inputActionTokenCounterHint'
    | 'inputActionMobileAuxiliaryAction'
    | 'inputActionMobileAuxiliaryActionHint'
    | 'exportToPdf'
    | 'exportToPdfHint'
    | 'toolApprovalRequired'
    | 'toolApprovalRequiredHint'
    | 'newConversationInheritLastSettings'
    | 'newConversationInheritLastSettingsHint'
    | 'voiceTitle'
    | 'voiceTtsModel'
    | 'voiceTtsModelAuto'
    | 'voiceTtsModelHint'
    | 'voiceSttModel'
    | 'voiceSttModelAuto'
    | 'voiceSttModelHint'
    | 'voiceTtsVoice'
    | 'voiceTtsVoicePlaceholder'
    | 'voiceTtsVoiceHint'
    | 'moreActions'
    | 'titleSave'
    | 'titleCancel'
    | 'refresh'
>;

const resolveInputActionsVoiceTemplateStrings = (sanitizer: SanitizerApi): InputActionsVoice => {
    return {
        notifyOnCompletion: i18n.html(sanitizer, 'chat.configuration.notify_on_completion'),
        notifyOnError: i18n.html(sanitizer, 'chat.configuration.notify_on_error'),
        notifyOnCompletionHint: i18n.html(sanitizer, 'chat.configuration.notifyOnCompletionHint'),
        notifyOnErrorHint: i18n.html(sanitizer, 'chat.configuration.notifyOnErrorHint'),
        microphoneSoundEffects: i18n.html(sanitizer, 'chat.configuration.microphoneSoundEffects'),
        microphoneSoundEffectsHint: i18n.html(sanitizer, 'chat.configuration.microphoneSoundEffectsHint'),
        inputActionsTitle: i18n.html(sanitizer, 'chat.configuration.inputActions.title'),
        inputActionVoice: i18n.html(sanitizer, 'chat.configuration.inputActions.voice'),
        inputActionVoiceHint: i18n.html(sanitizer, 'chat.configuration.inputActions.voiceHint'),
        inputActionCall: i18n.html(sanitizer, 'chat.configuration.inputActions.call'),
        inputActionCallHint: i18n.html(sanitizer, 'chat.configuration.inputActions.callHint'),
        inputActionUploadFile: i18n.html(sanitizer, 'chat.configuration.inputActions.uploadFile'),
        inputActionUploadFileHint: i18n.html(sanitizer, 'chat.configuration.inputActions.uploadFileHint'),
        inputActionCamera: i18n.html(sanitizer, 'chat.configuration.inputActions.camera'),
        inputActionCameraHint: i18n.html(sanitizer, 'chat.configuration.inputActions.cameraHint'),
        inputActionCharacterMap: i18n.html(sanitizer, 'chat.characterMap.preference'),
        inputActionCharacterMapHint: i18n.html(sanitizer, 'chat.characterMap.preferenceHint'),
        inputActionPrompts: i18n.html(sanitizer, 'chat.configuration.inputActions.prompts'),
        inputActionPromptsHint: i18n.html(sanitizer, 'chat.configuration.inputActions.promptsHint'),
        inputActionTokenCounter: i18n.html(sanitizer, 'chat.configuration.inputActions.tokenCounter'),
        inputActionTokenCounterHint: i18n.html(sanitizer, 'chat.configuration.inputActions.tokenCounterHint'),
        inputActionMobileAuxiliaryAction: i18n.html(sanitizer, 'chat.configuration.inputActions.auxiliary.label'),
        inputActionMobileAuxiliaryActionHint: i18n.html(sanitizer, 'chat.configuration.inputActions.auxiliary.hint'),
        exportToPdf: i18n.html(sanitizer, 'chat.configuration.inputActions.exportToPdf'),
        exportToPdfHint: i18n.html(sanitizer, 'chat.configuration.inputActions.exportToPdfHint'),
        toolApprovalRequired: i18n.html(sanitizer, 'chat.configuration.toolApprovalRequired'),
        toolApprovalRequiredHint: i18n.html(sanitizer, 'chat.configuration.toolApprovalRequiredHint'),
        newConversationInheritLastSettings: i18n.html(sanitizer, 'chat.configuration.newConversationInheritLastSettings'),
        newConversationInheritLastSettingsHint: i18n.html(sanitizer, 'chat.configuration.newConversationInheritLastSettingsHint'),
        voiceTitle: i18n.html(sanitizer, 'chat.configuration.voice.title'),
        voiceTtsModel: i18n.html(sanitizer, 'chat.configuration.voice.ttsModel'),
        voiceTtsModelAuto: i18n.html(sanitizer, 'chat.configuration.voice.ttsModelAuto'),
        voiceTtsModelHint: i18n.html(sanitizer, 'chat.configuration.voice.ttsModelHint'),
        voiceSttModel: i18n.html(sanitizer, 'chat.configuration.voice.sttModel'),
        voiceSttModelAuto: i18n.html(sanitizer, 'chat.configuration.voice.sttModelAuto'),
        voiceSttModelHint: i18n.html(sanitizer, 'chat.configuration.voice.sttModelHint'),
        voiceTtsVoice: i18n.html(sanitizer, 'chat.configuration.voice.ttsVoice'),
        voiceTtsVoicePlaceholder: i18n.attr(sanitizer, 'chat.configuration.voice.ttsVoicePlaceholder'),
        voiceTtsVoiceHint: i18n.html(sanitizer, 'chat.configuration.voice.ttsVoiceHint'),
        moreActions: i18n.attr(sanitizer, 'header.actions.moreActions'),
        titleSave: i18n.attr(sanitizer, 'common.save'),
        titleCancel: i18n.attr(sanitizer, 'common.cancel'),
        refresh: i18n.html(sanitizer, 'chat.configuration.refresh')
    };
};

export { resolveInputActionsVoiceTemplateStrings };
