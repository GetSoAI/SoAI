/* SoAI - Chat feature managed modal visibility [frontend/assets/ts/features/chat/conversationsettings/managedModalVisibility.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { isConversationAuthorityLocked } from '@core/chat/conversationAuthorityLock.ts';
import { isManagedConfigurationTabHidden } from '@features/chat/conversation/managedConversationCapabilities.ts';
import { CHAT_CONFIGURATION_TAB_DEFINITIONS, type ChatConfigurationTabId } from '@features/chat/conversationsettings/chatConfigurationTabs.ts';
import type { ConversationSettingsHost } from '@features/chat/conversationsettings/conversationSettingsHost.ts';
import type { Conversation } from '@features/chat/storage/storageModels.ts';

const setTabDefinitionVisibility = (host: ConversationSettingsHost, modal: Element, tabId: ChatConfigurationTabId, hidden: boolean): void => {
    const tabButton = dom.resolve(`[data-tab="${tabId}"]`, modal);
    if (!tabButton) {
        throw new Error(`Chat managed modal visibility missing required tab button ${tabId}`);
    }
    host.view.toggleClassName(tabButton, 'u-hidden', hidden);
    const definition = CHAT_CONFIGURATION_TAB_DEFINITIONS.find((entry) => entry.id === tabId);
    if (!definition) {
        throw new Error(`Chat managed modal visibility missing tab definition ${tabId}`);
    }
    const pane = dom.resolve(`[id="${definition.contentId}"]`, modal);
    if (!pane) {
        throw new Error(`Chat managed modal visibility missing required tab pane ${definition.contentId}`);
    }
    host.view.toggleClassName(pane, 'u-hidden', hidden);
};

const setConfigurationTabVisibility = (host: ConversationSettingsHost, modal: Element, managed: boolean): void => {
    for (const definition of CHAT_CONFIGURATION_TAB_DEFINITIONS) {
        setTabDefinitionVisibility(host, modal, definition.id, managed && isManagedConfigurationTabHidden(definition.id));
    }
};

const resolveActiveTabId = (modal: Element): ChatConfigurationTabId | null => {
    const activeTab = dom.resolve('.tabs-tab.is-active[data-tab]', modal);
    if (!activeTab) {
        return null;
    }
    const activeTabId = dom.getData(activeTab, 'tab');
    if (!activeTabId) {
        return null;
    }
    const definition = CHAT_CONFIGURATION_TAB_DEFINITIONS.find((entry) => entry.id === activeTabId);
    return definition ? definition.id : null;
};

const ensureVisibleActiveTab = (host: ConversationSettingsHost, modal: Element, managed: boolean): void => {
    if (!managed) {
        return;
    }
    const activeTabId = resolveActiveTabId(modal);
    if (activeTabId !== null && !isManagedConfigurationTabHidden(activeTabId)) {
        return;
    }
    host.workflow.activateConversationSettingsTab('general');
};

const applyManagedModalVisibility = (host: ConversationSettingsHost, modal: Element, conversation: Conversation | null): void => {
    const managed = isConversationAuthorityLocked(conversation);
    setConfigurationTabVisibility(host, modal, managed);
    ensureVisibleActiveTab(host, modal, managed);
};

export { applyManagedModalVisibility };
