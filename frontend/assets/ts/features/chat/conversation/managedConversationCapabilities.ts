/* SoAI - Chat feature managed conversation capabilities [frontend/assets/ts/features/chat/conversation/managedConversationCapabilities.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatConfigurationTabId } from '@features/chat/conversationsettings/chatConfigurationTabs.ts';

type ChatInputActionName = 'voice' | 'call' | 'fileUpload' | 'camera';

const MANAGED_HIDDEN_CONFIGURATION_TAB_IDS: ReadonlySet<ChatConfigurationTabId> = new Set(['completion', 'mcp', 'voice', 'files', 'knowledge']);

const isManagedConfigurationTabHidden = (tabId: ChatConfigurationTabId): boolean => MANAGED_HIDDEN_CONFIGURATION_TAB_IDS.has(tabId);

export { isManagedConfigurationTabHidden, MANAGED_HIDDEN_CONFIGURATION_TAB_IDS };
export type { ChatInputActionName };
