/* SoAI - Chat preset section catalog [frontend/assets/ts/features/chat/conversationsettings/chatPresetSections.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n, type TranslationKey } from '@core/i18n/index.ts';
import type { ChatConfigurationTabId } from '@features/chat/conversationsettings/chatConfigurationTabs.ts';

type ChatPresetSectionId = 'general' | 'appearance' | 'completion' | 'voice' | 'files' | 'knowledge' | 'tools';

interface ChatPresetSectionDefinition {
    id: ChatPresetSectionId;
    tabId: ChatConfigurationTabId;
    translationKey: TranslationKey;
    displayOrder: number;
}

const CHAT_PRESET_SECTION_DEFINITIONS: ReadonlyArray<ChatPresetSectionDefinition> = Object.freeze([
    { id: 'general', tabId: 'general', translationKey: 'chat.configuration.tabs.general', displayOrder: 0 },
    { id: 'appearance', tabId: 'appearance', translationKey: 'chat.configuration.tabs.appearance', displayOrder: 1 },
    { id: 'completion', tabId: 'completion', translationKey: 'chat.configuration.tabs.completion', displayOrder: 2 },
    { id: 'voice', tabId: 'voice', translationKey: 'chat.configuration.tabs.voice', displayOrder: 3 },
    { id: 'files', tabId: 'files', translationKey: 'chat.configuration.tabs.files', displayOrder: 4 },
    { id: 'knowledge', tabId: 'knowledge', translationKey: 'chat.configuration.tabs.knowledge', displayOrder: 5 },
    { id: 'tools', tabId: 'mcp', translationKey: 'chat.configuration.mcp.tools', displayOrder: 6 }
]);

const isChatPresetSectionId = (value: string): value is ChatPresetSectionId => CHAT_PRESET_SECTION_DEFINITIONS.some((section) => section.id === value);

const translateChatPresetSection = (sectionId: ChatPresetSectionId): string => {
    if (sectionId === 'general') return i18n.t('chat.configuration.tabs.general');
    if (sectionId === 'appearance') return i18n.t('chat.configuration.tabs.appearance');
    if (sectionId === 'completion') return i18n.t('chat.configuration.tabs.completion');
    if (sectionId === 'voice') return i18n.t('chat.configuration.tabs.voice');
    if (sectionId === 'files') return i18n.t('chat.configuration.tabs.files');
    if (sectionId === 'knowledge') return i18n.t('chat.configuration.tabs.knowledge');
    return i18n.t('chat.configuration.mcp.tools');
};

export { CHAT_PRESET_SECTION_DEFINITIONS, isChatPresetSectionId, translateChatPresetSection };
export type { ChatPresetSectionDefinition, ChatPresetSectionId };
