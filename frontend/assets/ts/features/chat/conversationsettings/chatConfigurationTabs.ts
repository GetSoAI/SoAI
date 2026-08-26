/* SoAI - Chat feature configuration tabs [frontend/assets/ts/features/chat/conversationsettings/chatConfigurationTabs.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { CHAT_CONFIGURATION_MODAL_ID } from '@features/chat/modals/constants.ts';

type ChatConfigurationTabId = 'general' | 'appearance' | 'files' | 'completion' | 'voice' | 'knowledge' | 'memory' | 'mcp' | 'presets';

interface ChatConfigurationTabDefinition {
    id: ChatConfigurationTabId;
    contentId: string;
}

const CHAT_CONFIGURATION_TAB_DEFINITIONS: ReadonlyArray<ChatConfigurationTabDefinition> = Object.freeze([
    { id: 'general', contentId: modalUiId(CHAT_CONFIGURATION_MODAL_ID, 'general-content') },
    { id: 'appearance', contentId: modalUiId(CHAT_CONFIGURATION_MODAL_ID, 'appearance-content') },
    { id: 'completion', contentId: modalUiId(CHAT_CONFIGURATION_MODAL_ID, 'completion-content') },
    { id: 'voice', contentId: modalUiId(CHAT_CONFIGURATION_MODAL_ID, 'voice-content') },
    { id: 'files', contentId: modalUiId(CHAT_CONFIGURATION_MODAL_ID, 'files-folder-content') },
    { id: 'knowledge', contentId: modalUiId(CHAT_CONFIGURATION_MODAL_ID, 'knowledge-content') },
    { id: 'memory', contentId: modalUiId(CHAT_CONFIGURATION_MODAL_ID, 'memory-content') },
    { id: 'mcp', contentId: modalUiId(CHAT_CONFIGURATION_MODAL_ID, 'mcp-content') },
    { id: 'presets', contentId: modalUiId(CHAT_CONFIGURATION_MODAL_ID, 'presets-content') }
]);

const CHAT_CONFIGURATION_PARAMETER_TAB_IDS: ReadonlySet<ChatConfigurationTabId> = new Set(['general', 'appearance', 'completion', 'voice']);

const isChatConfigurationTabId = (value: string): value is ChatConfigurationTabId => CHAT_CONFIGURATION_TAB_DEFINITIONS.some((entry) => entry.id === value);

const resolveChatConfigurationTabId = (candidate: string): ChatConfigurationTabId => (isChatConfigurationTabId(candidate) ? candidate : 'general');

const resolveChatConfigurationTabLabel = (tabId: ChatConfigurationTabId): string => {
    switch (tabId) {
        case 'general':
            return i18n.t('chat.configuration.tabs.general');
        case 'appearance':
            return i18n.t('chat.configuration.tabs.appearance');
        case 'completion':
            return i18n.t('chat.configuration.tabs.completion');
        case 'files':
            return i18n.t('chat.configuration.tabs.files');
        case 'voice':
            return i18n.t('chat.configuration.tabs.voice');
        case 'knowledge':
            return i18n.t('chat.configuration.tabs.knowledge');
        case 'memory':
            return i18n.t('chat.configuration.tabs.memory');
        case 'mcp':
            return i18n.t('chat.configuration.mcp.tools');
        case 'presets':
            return i18n.t('chat.configuration.tabs.presets');
    }
};

const isChatConfigurationParameterTabId = (tabId: string): boolean => {
    const resolved = resolveChatConfigurationTabId(tabId);
    return CHAT_CONFIGURATION_PARAMETER_TAB_IDS.has(resolved);
};

export { CHAT_CONFIGURATION_TAB_DEFINITIONS, isChatConfigurationParameterTabId, resolveChatConfigurationTabId, resolveChatConfigurationTabLabel };
export type { ChatConfigurationTabDefinition, ChatConfigurationTabId };
