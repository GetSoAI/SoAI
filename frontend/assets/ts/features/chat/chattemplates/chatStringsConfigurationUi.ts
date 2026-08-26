/* SoAI - Chat feature strings configuration UI [frontend/assets/ts/features/chat/chattemplates/chatStringsConfigurationUi.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SanitizerApi } from '@core/pagecontext/public.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ChatTemplateStringSet } from '@features/chat/chattemplates/stringSetTypes.ts';

type ConfigurationUi = Pick<
    ChatTemplateStringSet,
    | 'configurationTitle'
    | 'settingsLabel'
    | 'settingsLinkTitle'
    | 'closeLabel'
    | 'userName'
    | 'userNamePlaceholder'
    | 'assistantName'
    | 'assistantNamePlaceholder'
    | 'userAvatarLabel'
    | 'userAvatarUpload'
    | 'userAvatarRemove'
    | 'userAvatarHint'
    | 'assistantAvatarLabel'
    | 'assistantAvatarUpload'
    | 'assistantAvatarRemove'
    | 'assistantAvatarHint'
    | 'hideRealModel'
    | 'hideRealModelHint'
    | 'autoTitleGeneration'
    | 'autoTitleGenerationHint'
    | 'showActivities'
    | 'showActivitiesHint'
    | 'hideAutomationRuns'
    | 'hideAutomationRunsHint'
    | 'hideMessagingConversations'
    | 'hideMessagingConversationsHint'
    | 'systemPrompt'
    | 'systemPromptPlaceholder'
    | 'systemPromptLock'
    | 'systemPromptLockHint'
    | 'systemPromptLockLocked'
    | 'systemPromptLockUnlocked'
    | 'systemPromptLockLockedAttr'
    | 'systemPromptLockUnlockedAttr'
    | 'soaiSystemPrompt'
    | 'soaiSystemPromptHint'
    | 'save'
    | 'delete'
    | 'restore'
    | 'close'
    | 'saveCommon'
    | 'cancelCommon'
    | 'widescreenMode'
    | 'widescreenModeHint'
    | 'textZoom'
    | 'textZoomSmall'
    | 'textZoomNormal'
    | 'textZoomLarge'
    | 'richTextMode'
    | 'richTextModeHint'
    | 'inlineMultimediaPreviews'
    | 'inlineMultimediaPreviewsHint'
    | 'filesFolderTitle'
    | 'filesFolderDescription'
    | 'filesFolderCurrentLabel'
    | 'filesFolderChangeButton'
    | 'filesFolderResetButton'
>;

const resolveConfigurationUiTemplateStrings = (sanitizer: SanitizerApi): ConfigurationUi => {
    return {
        configurationTitle: i18n.html(sanitizer, 'chat.configuration.title'),
        settingsLabel: i18n.html(sanitizer, 'settings.title'),
        settingsLinkTitle: i18n.attr(sanitizer, 'header.actions.openSettings'),
        closeLabel: i18n.attr(sanitizer, 'common.close'),
        userName: i18n.html(sanitizer, 'chat.configuration.user_name'),
        userNamePlaceholder: i18n.attr(sanitizer, 'chat.configuration.userNamePlaceholder'),
        assistantName: i18n.html(sanitizer, 'chat.configuration.assistant_name'),
        assistantNamePlaceholder: i18n.attr(sanitizer, 'chat.configuration.assistantNamePlaceholder'),
        userAvatarLabel: i18n.html(sanitizer, 'chat.configuration.userAvatar'),
        userAvatarUpload: i18n.html(sanitizer, 'chat.configuration.userAvatarUpload'),
        userAvatarRemove: i18n.html(sanitizer, 'chat.configuration.userAvatarRemove'),
        userAvatarHint: i18n.html(sanitizer, 'chat.configuration.userAvatarHint'),
        assistantAvatarLabel: i18n.html(sanitizer, 'chat.configuration.assistantAvatar'),
        assistantAvatarUpload: i18n.html(sanitizer, 'chat.configuration.assistantAvatarUpload'),
        assistantAvatarRemove: i18n.html(sanitizer, 'chat.configuration.assistantAvatarRemove'),
        assistantAvatarHint: i18n.html(sanitizer, 'chat.configuration.assistantAvatarHint'),
        hideRealModel: i18n.html(sanitizer, 'chat.configuration.hide_real_model'),
        hideRealModelHint: i18n.html(sanitizer, 'chat.configuration.hideRealModelHint'),
        autoTitleGeneration: i18n.html(sanitizer, 'chat.configuration.autoTitleGeneration'),
        autoTitleGenerationHint: i18n.html(sanitizer, 'chat.configuration.autoTitleGenerationHint'),
        showActivities: i18n.html(sanitizer, 'chat.configuration.showActivities'),
        showActivitiesHint: i18n.html(sanitizer, 'chat.configuration.showActivitiesHint'),
        hideAutomationRuns: i18n.html(sanitizer, 'chat.configuration.hideAutomationRuns'),
        hideAutomationRunsHint: i18n.html(sanitizer, 'chat.configuration.hideAutomationRunsHint'),
        hideMessagingConversations: i18n.html(sanitizer, 'chat.configuration.hideMessagingConversations'),
        hideMessagingConversationsHint: i18n.html(sanitizer, 'chat.configuration.hideMessagingConversationsHint'),
        systemPrompt: i18n.html(sanitizer, 'chat.configuration.systemPrompt'),
        systemPromptPlaceholder: i18n.attr(sanitizer, 'chat.configuration.systemPromptPlaceholder'),
        systemPromptLock: i18n.html(sanitizer, 'chat.configuration.systemPromptLock'),
        systemPromptLockHint: i18n.html(sanitizer, 'chat.configuration.systemPromptLockHint'),
        systemPromptLockLocked: i18n.html(sanitizer, 'chat.configuration.systemPromptLockLocked'),
        systemPromptLockUnlocked: i18n.html(sanitizer, 'chat.configuration.systemPromptLockUnlocked'),
        systemPromptLockLockedAttr: i18n.attr(sanitizer, 'chat.configuration.systemPromptLockLocked'),
        systemPromptLockUnlockedAttr: i18n.attr(sanitizer, 'chat.configuration.systemPromptLockUnlocked'),
        soaiSystemPrompt: i18n.html(sanitizer, 'chat.configuration.soaiSystemPrompt'),
        soaiSystemPromptHint: i18n.html(sanitizer, 'chat.configuration.soaiSystemPromptHint'),
        save: i18n.html(sanitizer, 'chat.configuration.save'),
        delete: i18n.html(sanitizer, 'chat.configuration.delete'),
        restore: i18n.html(sanitizer, 'chat.configuration.restore'),
        close: i18n.html(sanitizer, 'chat.configuration.close'),
        saveCommon: i18n.html(sanitizer, 'common.save'),
        cancelCommon: i18n.html(sanitizer, 'common.cancel'),
        widescreenMode: i18n.html(sanitizer, 'chat.configuration.widescreen_mode'),
        widescreenModeHint: i18n.html(sanitizer, 'chat.configuration.widescreenModeHint'),
        textZoom: i18n.html(sanitizer, 'chat.configuration.text_zoom'),
        textZoomSmall: i18n.html(sanitizer, 'chat.configuration.textZoomSmall'),
        textZoomNormal: i18n.html(sanitizer, 'chat.configuration.textZoomNormal'),
        textZoomLarge: i18n.html(sanitizer, 'chat.configuration.textZoomLarge'),
        richTextMode: i18n.html(sanitizer, 'chat.configuration.richTextMode'),
        richTextModeHint: i18n.html(sanitizer, 'chat.configuration.richTextModeHint'),
        inlineMultimediaPreviews: i18n.html(sanitizer, 'chat.configuration.inlineMultimediaPreviews'),
        inlineMultimediaPreviewsHint: i18n.html(sanitizer, 'chat.configuration.inlineMultimediaPreviewsHint'),
        filesFolderTitle: i18n.html(sanitizer, 'chat.configuration.filesFolder.title'),
        filesFolderDescription: i18n.html(sanitizer, 'chat.configuration.filesFolder.description'),
        filesFolderCurrentLabel: i18n.html(sanitizer, 'chat.configuration.filesFolder.currentLabel'),
        filesFolderChangeButton: i18n.html(sanitizer, 'chat.configuration.filesFolder.changeButton'),
        filesFolderResetButton: i18n.html(sanitizer, 'chat.configuration.filesFolder.resetButton')
    };
};

export { resolveConfigurationUiTemplateStrings };
